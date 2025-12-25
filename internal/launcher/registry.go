package launcher

import (
	"fmt"
	"log"
	"os/exec"
	"strings"
	"syscall"
	"time"

	"github.com/sigma/locus-go/internal/apps"
	"github.com/sigma/locus-go/internal/config"
)

type LauncherUI interface {
	UpdateResults(items []*LauncherItem)
	HandleCommand(command string)
}

type LauncherContext struct {
	Config *config.Config
	UI     LauncherUI
}

// LauncherSizeMode represents launcher window size mode
type LauncherSizeMode int

const (
	LauncherSizeModeDefault LauncherSizeMode = iota
	LauncherSizeModeWallpaper
	LauncherSizeModeGrid
	LauncherSizeModeCustom
)

// LauncherItem represents a single result item
type LauncherItem struct {
	Title    string
	Subtitle string
	Icon     string
	Command  string
	Launcher Launcher
}

// Launcher is the interface that all launchers must implement
type Launcher interface {
	Name() string
	CommandTriggers() []string
	GetSizeMode() LauncherSizeMode
	Populate(query string, ctx *LauncherContext) []*LauncherItem
	HandlesEnter() bool
	HandleEnter(query string, ctx *LauncherContext) bool
	HandlesTab() bool
	HandleTab(query string) string
	Cleanup()
}

// LauncherRegistry manages all launchers
type LauncherRegistry struct {
	launchers    map[string]Launcher
	triggerMap   map[string]Launcher
	customPrefix map[string]string // name -> custom prefix
	config       *config.Config
	ctx          *LauncherContext
	searchCache  *SearchCache
	appsHash     string
}

// NewLauncherRegistry creates a new launcher registry
func NewLauncherRegistry(cfg *config.Config) *LauncherRegistry {
	cache, err := NewSearchCache(cfg.Launcher.Performance.SearchCacheSize)
	if err != nil {
		log.Printf("Failed to create search cache: %v", err)
		// Continue without cache rather than failing
		cache = nil
	}

	return &LauncherRegistry{
		launchers:    make(map[string]Launcher),
		triggerMap:   make(map[string]Launcher),
		customPrefix: make(map[string]string),
		config:       cfg,
		searchCache:  cache,
		appsHash:     "",
	}
}

// Register registers a launcher
func (r *LauncherRegistry) Register(launcher Launcher) error {
	name := launcher.Name()

	if _, exists := r.launchers[name]; exists {
		return fmt.Errorf("launcher '%s' already registered", name)
	}

	r.launchers[name] = launcher

	// Register triggers
	for _, trigger := range launcher.CommandTriggers() {
		r.triggerMap[trigger] = launcher
		log.Printf("Registered trigger: %s -> %s", trigger, name)
	}

	return nil
}

// RegisterWithCustomPrefix registers a launcher with custom prefix
func (r *LauncherRegistry) RegisterWithCustomPrefix(launcher Launcher, prefix string) error {
	name := launcher.Name()

	if err := r.Register(launcher); err != nil {
		return err
	}

	r.customPrefix[name] = prefix
	r.triggerMap[prefix] = launcher

	log.Printf("Registered custom prefix: %s -> %s", prefix, name)

	return nil
}

// Unregister unregisters a launcher
func (r *LauncherRegistry) Unregister(name string) {
	if launcher, exists := r.launchers[name]; exists {
		// Remove triggers
		for _, trigger := range launcher.CommandTriggers() {
			delete(r.triggerMap, trigger)
		}

		// Remove custom prefix
		if prefix, ok := r.customPrefix[name]; ok {
			delete(r.triggerMap, prefix)
			delete(r.customPrefix, name)
		}

		launcher.Cleanup()
		delete(r.launchers, name)

		log.Printf("Unregistered launcher: %s", name)
	}
}

// GetLauncher returns a launcher by trigger
func (r *LauncherRegistry) GetLauncher(trigger string) (Launcher, bool) {
	launcher, exists := r.triggerMap[trigger]
	return launcher, exists
}

// FindLauncherForInput finds a launcher for given input
func (r *LauncherRegistry) FindLauncherForInput(input string) (trigger string, launcher Launcher, query string) {
	// Check for > prefix
	if strings.HasPrefix(input, ">") {
		parts := strings.SplitN(input[1:], " ", 2)
		if len(parts) > 0 {
			trigger = parts[0]
			if len(parts) > 1 {
				query = parts[1]
			}

			launcher, exists := r.GetLauncher(trigger)
			if exists {
				return trigger, launcher, query
			}
		}
	}

	// Check for colon-style triggers (f:, wp:, etc.)
	if strings.Contains(input, ":") {
		parts := strings.SplitN(input, ":", 2)
		if len(parts) > 1 {
			trigger = parts[0]
			query = strings.TrimSpace(parts[1])

			launcher, exists := r.GetLauncher(trigger)
			if exists {
				return trigger, launcher, query
			}
		}
	}

	// Check for space-style triggers (f , m , etc.)
	if strings.Contains(input, " ") {
		parts := strings.SplitN(input, " ", 2)
		if len(parts) > 1 {
			trigger = parts[0]
			query = strings.TrimSpace(parts[1])

			launcher, exists := r.GetLauncher(trigger)
			if exists {
				return trigger, launcher, query
			}
		}
	}

	return "", nil, ""
}

// GetAllLaunchers returns all registered launchers
func (r *LauncherRegistry) GetAllLaunchers() []Launcher {
	launchers := make([]Launcher, 0, len(r.launchers))
	for _, launcher := range r.launchers {
		launchers = append(launchers, launcher)
	}
	return launchers
}

// Cleanup cleans up all launchers
func (r *LauncherRegistry) Cleanup() {
	for name, launcher := range r.launchers {
		launcher.Cleanup()
		log.Printf("Cleaned up launcher: %s", name)
	}

	r.launchers = make(map[string]Launcher)
	r.triggerMap = make(map[string]Launcher)
	r.customPrefix = make(map[string]string)

	// Clear search cache
	if r.searchCache != nil {
		r.searchCache.Invalidate()
	}
	r.appsHash = ""
}

// Search searches for items matching the query
func (r *LauncherRegistry) Search(query string) ([]*LauncherItem, error) {
	startTime := time.Now()
	log.Printf("[REGISTRY-SEARCH] Started for query='%s'", query)

	_, l, q := r.FindLauncherForInput(query)

	if l != nil {
		// Launcher-specific search - only search this launcher
		log.Printf("[REGISTRY-SEARCH] Launcher-specific search: launcher='%s', query='%s'", l.Name(), q)
		populateStart := time.Now()
		items := l.Populate(q, r.ctx)
		log.Printf("[REGISTRY-SEARCH] Launcher-specific populate completed in %v, %d items", time.Since(populateStart), len(items))

		// Apply max results limit
		maxResults := r.config.Launcher.Search.MaxResults
		if len(items) > maxResults {
			items = items[:maxResults]
			log.Printf("[REGISTRY-SEARCH] Limited results to %d (max configured)", maxResults)
		}

		// Don't cache launcher-specific searches
		log.Printf("[REGISTRY-SEARCH] Completed launcher-specific search in %v", time.Since(startTime))
		return items, nil
	}

	// General app search - check cache first
	if r.searchCache != nil {
		cacheCheckStart := time.Now()
		if cachedResults, found := r.searchCache.Get(query, r.appsHash); found {
			log.Printf("[REGISTRY-SEARCH] Cache HIT for query='%s', returned %d items in %v", query, len(cachedResults), time.Since(cacheCheckStart))
			return cachedResults, nil
		}
		log.Printf("[REGISTRY-SEARCH] Cache MISS for query='%s' in %v", query, time.Since(cacheCheckStart))
	} else {
		log.Printf("[REGISTRY-SEARCH] No cache available")
	}

	// Find app launcher and search it (only search apps for general queries)
	var items []*LauncherItem
	var appLauncher Launcher

	for _, l := range r.launchers {
		if l.Name() == "apps" {
			appLauncher = l
			break
		}
	}

	if appLauncher != nil {
		log.Printf("[REGISTRY-SEARCH] Using AppLauncher for general query='%s'", query)
		populateStart := time.Now()
		items = appLauncher.Populate(query, r.ctx)
		log.Printf("[REGISTRY-SEARCH] AppLauncher populate completed in %v, %d items", time.Since(populateStart), len(items))
	} else {
		// Fallback: search all launchers (shouldn't happen)
		log.Printf("[REGISTRY-SEARCH] WARNING: No AppLauncher found, falling back to all launchers")
		for _, launcher := range r.launchers {
			launcherItems := launcher.Populate(query, r.ctx)
			items = append(items, launcherItems...)
		}
	}

	// Deduplicate results
	originalCount := len(items)
	items = r.deduplicateResults(items)
	if len(items) != originalCount {
		log.Printf("[REGISTRY-SEARCH] Deduplication removed %d duplicates (%d -> %d)", originalCount-len(items), originalCount, len(items))
	}

	// Apply max results limit
	maxResults := r.config.Launcher.Search.MaxResults
	if len(items) > maxResults {
		items = items[:maxResults]
		log.Printf("[REGISTRY-SEARCH] Limited results to %d (max configured)", maxResults)
	}

	// Cache the results if cache is available
	if r.searchCache != nil {
		durationMs := float64(time.Since(startTime).Nanoseconds()) / 1e6
		r.searchCache.Put(query, r.appsHash, items, durationMs)
		log.Printf("[REGISTRY-SEARCH] Cached results for query='%s' (duration=%.2fms)", query, durationMs)
	}

	log.Printf("[REGISTRY-SEARCH] Completed general search in %v, final result count: %d", time.Since(startTime), len(items))
	return items, nil
}

// deduplicateResults removes duplicate results based on title and subtitle
func (r *LauncherRegistry) deduplicateResults(items []*LauncherItem) []*LauncherItem {
	seen := make(map[string]bool)
	result := make([]*LauncherItem, 0, len(items))

	for _, item := range items {
		// Create unique key based on title and subtitle
		key := item.Title + "|" + item.Subtitle
		if !seen[key] {
			seen[key] = true
			result = append(result, item)
		}
	}

	return result
}

// UpdateAppsHash updates the apps hash for cache invalidation
func (r *LauncherRegistry) UpdateAppsHash(apps []apps.App) {
	if r.searchCache != nil {
		r.appsHash = ComputeAppsHash(apps)
	}
}

// UpdateAppsHashFromLauncher updates the apps hash from the AppLauncher
func (r *LauncherRegistry) UpdateAppsHashFromLauncher() {
	if r.searchCache != nil {
		for _, launcher := range r.launchers {
			if appLauncher, ok := launcher.(*AppLauncher); ok {
				r.appsHash = appLauncher.GetAppsHash()
				break
			}
		}
	}
}

// GetCacheStats returns current cache statistics
func (r *LauncherRegistry) GetCacheStats() *CacheStats {
	if r.searchCache != nil {
		return r.searchCache.GetStats()
	}
	return nil
}

// Execute executes a launcher item
func (r *LauncherRegistry) Execute(item *LauncherItem) error {
	if item.Launcher != nil {
		if item.Launcher.HandlesEnter() {
			if item.Launcher.HandleEnter(item.Command, r.ctx) {
				return nil
			}
		}
	}

	if item.Command != "" {
		parts := strings.Fields(item.Command)
		if len(parts) == 0 {
			return fmt.Errorf("empty command")
		}

		cmd := exec.Command(parts[0], parts[1:]...)
		cmd.SysProcAttr = &syscall.SysProcAttr{
			Setsid: true,
		}

		if err := cmd.Start(); err != nil {
			return fmt.Errorf("failed to start command: %w", err)
		}

		return nil
	}

	return fmt.Errorf("no executable command")
}

// LoadBuiltIn loads built-in launchers
func (r *LauncherRegistry) LoadBuiltIn() error {
	r.ctx = &LauncherContext{
		Config: r.config,
	}

	launchers := []Launcher{
		NewAppLauncher(r.config), // App launcher first for priority
		NewShellLauncher(),
		NewWebLauncher(),
		NewCalcLauncher(),
		NewBrightnessLauncher(r.config),
		NewScreenshotLauncher(r.config),
		NewLockLauncher(r.config),
		NewTimerLauncher(r.config),
		NewKillLauncher(r.config),
		NewWMFocusLauncher(r.config),
		NewWallpaperLauncher(r.config),
		NewClipboardLauncher(r.config),
		NewWifiLauncher(r.config),
		NewFileLauncher(r.config),
	}

	for _, l := range launchers {
		if err := r.Register(l); err != nil {
			log.Printf("Failed to register launcher %s: %v", l.Name(), err)
		}
	}

	// Update apps hash after registration
	r.UpdateAppsHashFromLauncher()

	return nil
}
