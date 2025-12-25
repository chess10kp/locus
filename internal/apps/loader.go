package apps

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"os/user"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/sigma/locus-go/internal/config"
)

// expandPath expands ~ to home directory
func expandPath(path string) string {
	if len(path) > 0 && path[0] == '~' {
		home, err := user.Current()
		if err == nil {
			return filepath.Join(home.HomeDir, path[1:])
		}
	}
	return path
}

// App represents a desktop application
type App struct {
	Name        string `json:"name"`
	Exec        string `json:"exec"`
	Icon        string `json:"icon"`
	File        string `json:"file"`
	Category    string `json:"category"`
	Keywords    string `json:"keywords"`
	Description string `json:"description"`
	NoDisplay   bool   `json:"no_display"`
}

// AppLoader loads and caches desktop applications
type AppLoader struct {
	apps       []App
	cacheDir   string
	cacheFile  string
	cacheValid bool
	mu         sync.RWMutex
	cfg        *config.Config
}

// NewAppLoader creates a new app loader
func NewAppLoader(cfg *config.Config) *AppLoader {
	cacheDir := expandPath(cfg.Launcher.Cache.CacheDir)
	if cacheDir == "" || cacheDir == "~/.cache/locus" {
		home, _ := user.Current()
		cacheDir = filepath.Join(home.HomeDir, ".cache", "locus")
	}

	cacheFile := filepath.Join(cacheDir, cfg.Launcher.Cache.AppsCacheFile)

	return &AppLoader{
		apps:       []App{},
		cacheDir:   cacheDir,
		cacheFile:  cacheFile,
		cacheValid: false,
		cfg:        cfg,
	}
}

// LoadApps loads applications from cache or system
func (l *AppLoader) LoadApps(forceReload bool) ([]App, error) {
	l.mu.Lock()
	defer l.mu.Unlock()

	// Try loading from cache first
	if !forceReload && l.loadFromCache() {
		return l.apps, nil
	}

	// Load from system
	if err := l.loadFromSystem(); err != nil {
		return nil, err
	}

	// Save to cache
	l.saveToCache()

	return l.apps, nil
}

// loadFromCache loads apps from cache file
func (l *AppLoader) loadFromCache() bool {
	data, err := os.ReadFile(l.cacheFile)
	if err != nil {
		return false
	}

	var cache struct {
		Apps      []App  `json:"apps"`
		Timestamp string `json:"timestamp"`
		Version   string `json:"version"`
	}

	if err := json.Unmarshal(data, &cache); err != nil {
		return false
	}

	// Check cache age
	cacheTime, _ := time.Parse(time.RFC3339, cache.Timestamp)
	age := time.Since(cacheTime)

	// Cache is valid if less than 6 hours old
	if age.Hours() < float64(l.cfg.Launcher.Performance.CacheMaxAgeHours) {
		l.apps = cache.Apps
		l.cacheValid = true
		return true
	}

	return false
}

// saveToCache saves apps to cache file
func (l *AppLoader) saveToCache() error {
	// Ensure cache directory exists
	if err := os.MkdirAll(l.cacheDir, 0755); err != nil {
		return err
	}

	cache := struct {
		Apps      []App  `json:"apps"`
		Timestamp string `json:"timestamp"`
		Version   string `json:"version"`
	}{
		Apps:      l.apps,
		Timestamp: time.Now().Format(time.RFC3339),
		Version:   "1.0",
	}

	data, err := json.MarshalIndent(cache, "", "  ")
	if err != nil {
		return err
	}

	// Atomic write
	tempFile := l.cacheFile + ".tmp"
	if err := os.WriteFile(tempFile, data, 0644); err != nil {
		return err
	}

	return os.Rename(tempFile, l.cacheFile)
}

// loadFromSystem loads applications from .desktop files
func (l *AppLoader) loadFromSystem() error {
	var apps []App
	loadedFiles := make(map[string]bool)

	// Search paths
	searchPaths := []string{
		filepath.Join(os.Getenv("HOME"), ".local", "share", "applications"),
		"/usr/share/applications",
		"/usr/local/share/applications",
	}

	for _, searchPath := range searchPaths {
		if err := filepath.Walk(searchPath, func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return nil
			}

			// Skip directories
			if info.IsDir() {
				return nil
			}

			// Only process .desktop files
			if !strings.HasSuffix(path, ".desktop") {
				return nil
			}

			// Skip already loaded files
			if loadedFiles[path] {
				return nil
			}

			app, err := l.parseDesktopFile(path)
			if err == nil && !app.NoDisplay {
				apps = append(apps, app)
				loadedFiles[path] = true
			}

			return nil
		}); err != nil {
			continue
		}
	}

	// Sort apps by name
	sort.Slice(apps, func(i, j int) bool {
		return strings.ToLower(apps[i].Name) < strings.ToLower(apps[j].Name)
	})

	l.apps = apps
	l.cacheValid = true

	fmt.Printf("Loaded %d applications\n", len(apps))

	return nil
}

// parseDesktopFile parses a single .desktop file
func (l *AppLoader) parseDesktopFile(path string) (App, error) {
	file, err := os.Open(path)
	if err != nil {
		return App{}, err
	}
	defer file.Close()

	app := App{
		File: path,
	}

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())

		// Skip comments and empty lines
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}

		// Parse key=value pairs
		if strings.Contains(line, "=") {
			parts := strings.SplitN(line, "=", 2)
			if len(parts) != 2 {
				continue
			}

			key := strings.TrimSpace(parts[0])
			value := strings.TrimSpace(parts[1])

			// Unquote value
			value = strings.Trim(value, "\"")

			switch key {
			case "Name":
				app.Name = value
			case "Exec":
				app.Exec = value
			case "Icon":
				app.Icon = value
			case "Type":
				if value != "Application" {
					app.NoDisplay = true
				}
			case "NoDisplay":
				app.NoDisplay = strings.ToLower(value) == "true"
			case "Hidden":
				if strings.ToLower(value) == "true" {
					app.NoDisplay = true
				}
			case "Keywords":
				app.Keywords = value
			case "Comment":
				if app.Description == "" {
					app.Description = value
				}
			}
		}
	}

	// Validate app has required fields
	if app.Name == "" || app.Exec == "" {
		return App{}, fmt.Errorf("invalid desktop file: missing Name or Exec")
	}

	return app, nil
}

// Search searches applications by name
func (l *AppLoader) Search(query string, maxResults int) []App {
	l.mu.RLock()
	defer l.mu.RUnlock()

	if query == "" {
		// Return first maxResults apps
		if len(l.apps) > maxResults {
			return l.apps[:maxResults]
		}
		return l.apps
	}

	query = strings.ToLower(query)

	var results []App
	for _, app := range l.apps {
		// Simple substring match for now
		// TODO: Implement fuzzy search
		name := strings.ToLower(app.Name)
		exec := strings.ToLower(app.Exec)

		if strings.Contains(name, query) || strings.Contains(exec, query) {
			results = append(results, app)
		}

		if len(results) >= maxResults {
			break
		}
	}

	return results
}

// GetApps returns all loaded applications
func (l *AppLoader) GetApps() []App {
	l.mu.RLock()
	defer l.mu.RUnlock()

	apps := make([]App, len(l.apps))
	copy(apps, l.apps)
	return apps
}

// InvalidateCache marks cache as invalid
func (l *AppLoader) InvalidateCache() {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.cacheValid = false
}
