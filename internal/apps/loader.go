package apps

import (
	"bufio"
	"encoding/json"
	"fmt"
	"log"
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
	loadStart := time.Now()
	l.mu.Lock()
	defer l.mu.Unlock()

	fmt.Printf("[APPS-LOADER] LoadApps started (forceReload=%v)\n", forceReload)

	// Try loading from cache first
	if !forceReload && l.loadFromCache() {
		totalTime := time.Since(loadStart)
		fmt.Printf("[APPS-LOADER] LoadApps completed from cache in %v\n", totalTime)
		return l.apps, nil
	}

	fmt.Printf("[APPS-LOADER] Loading apps from system directories...\n")

	// Load from system
	if err := l.loadFromSystem(); err != nil {
		return nil, fmt.Errorf("failed to load apps from system: %w", err)
	}

	// Save to cache
	if saveErr := l.saveToCache(); saveErr != nil {
		fmt.Printf("[APPS-LOADER] Warning: failed to save cache: %v\n", saveErr)
		// Continue even if cache save fails
	}

	totalTime := time.Since(loadStart)
	fmt.Printf("[APPS-LOADER] LoadApps completed from system in %v\n", totalTime)
	return l.apps, nil
}

// loadFromCache loads apps from cache file
func (l *AppLoader) loadFromCache() bool {
	loadStart := time.Now()
	data, err := os.ReadFile(l.cacheFile)
	if err != nil {
		fmt.Printf("[APPS-CACHE] Cache miss: file not found or unreadable\n")
		return false
	}

	var cache struct {
		Apps      []App  `json:"apps"`
		Timestamp string `json:"timestamp"`
		Version   string `json:"version"`
	}

	if err := json.Unmarshal(data, &cache); err != nil {
		fmt.Printf("[APPS-CACHE] Cache miss: failed to unmarshal cache file: %v\n", err)
		return false
	}

	// Check cache age
	cacheTime, _ := time.Parse(time.RFC3339, cache.Timestamp)
	age := time.Since(cacheTime)
	maxAgeHours := float64(l.cfg.Launcher.Performance.CacheMaxAgeHours)

	// Cache is valid if less than max age hours old
	if age.Hours() < maxAgeHours {
		l.apps = cache.Apps
		l.cacheValid = true
		loadTime := time.Since(loadStart)
		fmt.Printf("[APPS-CACHE] Cache hit: loaded %d apps from cache in %v (age: %v)\n", len(cache.Apps), loadTime, age)
		return true
	}

	fmt.Printf("[APPS-CACHE] Cache miss: cache expired (age: %v, max: %vh)\n", age, maxAgeHours)
	return false
}

// saveToCache saves apps to cache file
func (l *AppLoader) saveToCache() error {
	saveStart := time.Now()

	// Ensure cache directory exists
	if err := os.MkdirAll(l.cacheDir, 0755); err != nil {
		return fmt.Errorf("failed to create cache directory: %w", err)
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
		return fmt.Errorf("failed to marshal cache data: %w", err)
	}

	// Atomic write
	tempFile := l.cacheFile + ".tmp"
	if err := os.WriteFile(tempFile, data, 0644); err != nil {
		return fmt.Errorf("failed to write temp cache file: %w", err)
	}

	if err := os.Rename(tempFile, l.cacheFile); err != nil {
		return fmt.Errorf("failed to rename temp cache file: %w", err)
	}

	saveTime := time.Since(saveStart)
	fmt.Printf("[APPS-CACHE] Cache saved: %d apps in %v\n", len(l.apps), saveTime)
	return nil
}

// loadFromSystem loads applications from .desktop files
func (l *AppLoader) loadFromSystem() error {
	start := time.Now()
	var apps []App
	loadedFiles := make(map[string]bool)

	// Search paths
	searchPaths := []string{
		filepath.Join(os.Getenv("HOME"), ".local", "share", "applications"),
		"/usr/share/applications",
		"/usr/local/share/applications",
	}

	var wg sync.WaitGroup
	appChan := make(chan App, 100)       // Buffered channel for results
	semaphore := make(chan struct{}, 10) // Limit parallel parsing

	// Collect all .desktop files first
	var desktopFiles []string
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

			desktopFiles = append(desktopFiles, path)
			loadedFiles[path] = true
			return nil
		}); err != nil {
			continue
		}
	}

	log.Printf("Found %d .desktop files, parsing in parallel", len(desktopFiles))

	// Parse files in parallel
	for _, filePath := range desktopFiles {
		wg.Add(1)
		go func(fp string) {
			defer wg.Done()

			// Acquire semaphore to limit concurrent parsing
			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			app, err := l.parseDesktopFile(fp)
			if err == nil && !app.NoDisplay {
				appChan <- app
			}
		}(filePath)
	}

	// Close channel when all parsing is done
	go func() {
		wg.Wait()
		close(appChan)
	}()

	// Collect results
	for app := range appChan {
		apps = append(apps, app)
	}

	// Sort apps by name
	sort.Slice(apps, func(i, j int) bool {
		return strings.ToLower(apps[i].Name) < strings.ToLower(apps[j].Name)
	})

	l.apps = apps
	l.cacheValid = true

	log.Printf("Loaded %d applications in %v (parallel parsing)", len(apps), time.Since(start))
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
