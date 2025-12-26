package launcher

import (
	"fmt"
	"log"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/sahilm/fuzzy"
	"github.com/sigma/locus-go/internal/apps"
	"github.com/sigma/locus-go/internal/config"
)

type AppLauncher struct {
	config     *config.Config
	appLoader  *apps.AppLoader
	apps       []apps.App
	appsLoaded bool
	mu         sync.RWMutex
	// Pre-computed search data for performance
	appNames    []string
	nameToApp   map[string]apps.App
	initialized bool
}

func NewAppLauncher(cfg *config.Config) *AppLauncher {
	return &AppLauncher{
		config:    cfg,
		appLoader: apps.NewAppLoader(cfg),
		apps:      []apps.App{},
	}
}

// StartBackgroundLoad starts loading apps in a background goroutine
func (l *AppLauncher) StartBackgroundLoad() {
	go func() {
		log.Printf("[APP-LAUNCHER] Starting background app loading")
		loadStart := time.Now()

		if _, err := l.appLoader.LoadApps(false); err != nil {
			log.Printf("[APP-LAUNCHER] Background app load failed: %v", err)
			return
		}

		l.mu.Lock()
		l.apps = l.appLoader.GetApps()
		l.appsLoaded = true

		// Pre-compute search data for performance
		l.precomputeSearchData()
		l.initialized = true

		l.mu.Unlock()

		log.Printf("[APP-LAUNCHER] Background load completed in %v, loaded %d apps", time.Since(loadStart), len(l.apps))
	}()
}

// precomputeSearchData creates optimized data structures for fast searching
func (l *AppLauncher) precomputeSearchData() {
	start := time.Now()

	// Pre-allocate with correct capacity
	l.appNames = make([]string, len(l.apps))
	l.nameToApp = make(map[string]apps.App, len(l.apps))

	for i, app := range l.apps {
		l.appNames[i] = app.Name
		l.nameToApp[app.Name] = app
	}

	log.Printf("[APP-LAUNCHER] Precomputed search data in %v", time.Since(start))
}

func (l *AppLauncher) Name() string {
	return "apps"
}

func (l *AppLauncher) CommandTriggers() []string {
	// No triggers - this is the default/general search launcher
	return []string{}
}

func (l *AppLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *AppLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	populateStart := time.Now()
	log.Printf("[APP-LAUNCHER] Populate started for query='%s'", query)

	l.mu.Lock()
	defer l.mu.Unlock()

	// Return empty results if apps haven't loaded yet (non-blocking)
	if !l.appsLoaded || !l.initialized {
		log.Printf("[APP-LAUNCHER] Apps not loaded yet, returning empty results")
		return []*LauncherItem{}
	}

	query = strings.TrimSpace(query)
	if query == "" {
		// Return top apps by name (alphabetical)
		maxResults := l.config.Launcher.Search.MaxResults
		topApps := l.apps
		if len(topApps) > maxResults {
			topApps = topApps[:maxResults]
		}
		log.Printf("[APP-LAUNCHER] Empty query, returning %d top apps", len(topApps))
		return l.appsToItems(topApps)
	}

	// Use fuzzy search
	maxResults := l.config.Launcher.Search.MaxResults
	results := l.fuzzySearch(query, maxResults)
	log.Printf("[APP-LAUNCHER] Fuzzy search completed in %v, returned %d results", time.Since(populateStart), len(results))
	return results
}

func (l *AppLauncher) fuzzySearch(query string, maxResults int) []*LauncherItem {
	fuzzyStart := time.Now()
	log.Printf("[APP-LAUNCHER] Fuzzy search started for query='%s' against %d apps", query, len(l.apps))

	// Use pre-computed data structures for performance
	findStart := time.Now()
	matches := fuzzy.Find(query, l.appNames)
	log.Printf("[APP-LAUNCHER] Fuzzy find completed in %v, found %d raw matches", time.Since(findStart), len(matches))

	// Adaptive score threshold based on query length
	minScore := 0
	if len(query) == 1 {
		minScore = 60 // Stricter for single character
	} else if len(query) == 2 {
		minScore = 40
	} else {
		minScore = 20
	}

	// Early cutoff - only consider top results
	maxConsider := maxResults * 2
	if len(matches) > maxConsider {
		matches = matches[:maxConsider]
	}

	// Filter by minimum score threshold
	queryLower := strings.ToLower(query)
	filteredMatches := make([]fuzzy.Match, 0, len(matches))

	for _, match := range matches {
		if match.Score >= minScore {
			filteredMatches = append(filteredMatches, match)
		}
	}

	log.Printf("[APP-LAUNCHER] After score filtering (>= %d): %d matches", minScore, len(filteredMatches))

	// Sort matches: prioritize exact prefix matches, then by fuzzy score
	sortStart := time.Now()
	sort.Slice(filteredMatches, func(i, j int) bool {
		match1 := filteredMatches[i]
		match2 := filteredMatches[j]

		// Pre-compute lowercase comparison
		match1StartsWith := strings.HasPrefix(strings.ToLower(match1.Str), queryLower)
		match2StartsWith := strings.HasPrefix(strings.ToLower(match2.Str), queryLower)

		// Prioritize exact prefix matches
		if match1StartsWith != match2StartsWith {
			return match1StartsWith
		}

		return match1.Score > match2.Score
	})
	log.Printf("[APP-LAUNCHER] Sorting completed in %v", time.Since(sortStart))

	// Convert matches to LauncherItems (limit to maxResults)
	items := make([]*LauncherItem, 0, min(len(filteredMatches), maxResults))

	for i := 0; i < len(filteredMatches) && i < maxResults; i++ {
		match := filteredMatches[i]
		if app, ok := l.nameToApp[match.Str]; ok {
			items = append(items, l.appToItem(app))
		}
	}

	log.Printf("[APP-LAUNCHER] Fuzzy search completed in %v, returning %d items", time.Since(fuzzyStart), len(items))
	return items
}

func (l *AppLauncher) appToItem(app apps.App) *LauncherItem {
	icon := app.Icon
	if icon == "" {
		icon = l.config.Launcher.Icons.FallbackIcon
	}

	// Build subtitle from description only, trimmed to first 10 characters
	subtitle := app.Description
	if len(subtitle) > 10 {
		subtitle = subtitle[:10] + "..."
	}

	return &LauncherItem{
		Title:      app.Name,
		Subtitle:   subtitle,
		Icon:       icon,
		ActionData: NewDesktopAction(app.File),
		Launcher:   l,
	}
}

func (l *AppLauncher) appsToItems(apps []apps.App) []*LauncherItem {
	items := make([]*LauncherItem, 0, len(apps))
	for _, app := range apps {
		items = append(items, l.appToItem(app))
	}
	return items
}

func (l *AppLauncher) HandlesEnter() bool {
	return false
}

func (l *AppLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	return false
}

func (l *AppLauncher) HandlesTab() bool {
	return false
}

func (l *AppLauncher) HandleTab(query string) string {
	return query
}

func (l *AppLauncher) Cleanup() {
}

// GetAppsHash returns the hash of currently loaded apps
func (l *AppLauncher) GetAppsHash() string {
	l.mu.RLock()
	defer l.mu.RUnlock()

	if !l.appsLoaded {
		return ""
	}

	return ComputeAppsHash(l.apps)
}

func (l *AppLauncher) GetHooks() []Hook {
	return []Hook{} // App launcher doesn't need custom hooks
}

func (l *AppLauncher) Rebuild(ctx *LauncherContext) error {
	// Reload apps from disk
	l.mu.Lock()
	defer l.mu.Unlock()

	apps, err := l.appLoader.LoadApps(true)
	if err != nil {
		return fmt.Errorf("failed to reload apps: %w", err)
	}

	l.apps = apps
	l.appsLoaded = true

	log.Printf("[APP-LAUNCHER] Rebuilt: loaded %d apps", len(apps))
	return nil
}

// Helper function for min
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
