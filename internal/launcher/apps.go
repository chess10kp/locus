package launcher

import (
	"fmt"
	"log"
	"os/exec"
	"sort"
	"strings"
	"sync"
	"syscall"
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
}

func NewAppLauncher(cfg *config.Config) *AppLauncher {
	return &AppLauncher{
		config:    cfg,
		appLoader: apps.NewAppLoader(cfg),
		apps:      []apps.App{},
	}
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

	// Load apps if not already loaded
	if !l.appsLoaded {
		loadStart := time.Now()
		log.Printf("[APP-LAUNCHER] Loading apps for first time")
		if _, err := l.appLoader.LoadApps(false); err != nil {
			log.Printf("[APP-LAUNCHER] Failed to load apps: %v", err)
			fmt.Printf("Failed to load apps: %v\n", err)
			return []*LauncherItem{}
		}
		l.apps = l.appLoader.GetApps()
		l.appsLoaded = true
		log.Printf("[APP-LAUNCHER] Loaded %d apps in %v", len(l.apps), time.Since(loadStart))
	}

	query = strings.TrimSpace(query)
	if query == "" {
		// Return top apps by name (alphabetical)
		maxResults := l.config.Launcher.Search.MaxResults
		if len(l.apps) > maxResults {
			l.apps = l.apps[:maxResults]
		}
		log.Printf("[APP-LAUNCHER] Empty query, returning %d top apps", len(l.apps))
		return l.appsToItems(l.apps)
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

	// Create list of app names for fuzzy matching
	appNames := make([]string, len(l.apps))
	nameToApp := make(map[string]apps.App)

	for i, app := range l.apps {
		appNames[i] = app.Name
		nameToApp[app.Name] = app
	}

	// Use fuzzy search with score threshold
	findStart := time.Now()
	matches := fuzzy.Find(query, appNames)
	log.Printf("[APP-LAUNCHER] Fuzzy find completed in %v, found %d raw matches", time.Since(findStart), len(matches))

	// Filter by minimum score threshold (25% like Python implementation)
	minScore := 25 // 25% of max score (100)
	filteredMatches := make([]fuzzy.Match, 0)

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

		// Check if match1 starts with query (exact prefix)
		match1StartsWith := strings.HasPrefix(strings.ToLower(match1.Str), strings.ToLower(query))
		match2StartsWith := strings.HasPrefix(strings.ToLower(match2.Str), strings.ToLower(query))

		// Prioritize exact prefix matches
		if match1StartsWith != match2StartsWith {
			return match1StartsWith
		}

		// Then sort by score (descending)
		return match1.Score > match2.Score
	})
	log.Printf("[APP-LAUNCHER] Sorting completed in %v", time.Since(sortStart))

	// Convert matches to LauncherItems (limit to maxResults)
	items := make([]*LauncherItem, 0, min(len(filteredMatches), maxResults))

	for i := 0; i < len(filteredMatches) && i < maxResults; i++ {
		match := filteredMatches[i]
		if app, ok := nameToApp[match.Str]; ok {
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

	// Build subtitle from description and keywords
	subtitle := app.Description
	if subtitle == "" && app.Keywords != "" {
		subtitle = fmt.Sprintf("Keywords: %s", app.Keywords)
	} else if subtitle != "" && app.Keywords != "" {
		subtitle = fmt.Sprintf("%s (%s)", subtitle, app.Keywords)
	}

	return &LauncherItem{
		Title:      app.Name,
		Subtitle:   subtitle,
		Icon:       icon,
		ActionData: NewShellAction(app.Exec),
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
	return true
}

func (l *AppLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	// For app execution, we need to handle field codes like %u, %f, etc.
	// Most desktop apps don't use these, but we should handle them properly

	// For now, just execute the command directly
	// TODO: Implement field code replacement if needed
	if query != "" {
		parts := strings.Fields(query)
		if len(parts) == 0 {
			return false
		}

		cmd := exec.Command(parts[0], parts[1:]...)
		cmd.SysProcAttr = &syscall.SysProcAttr{
			Setsid: true,
		}

		if err := cmd.Start(); err != nil {
			fmt.Printf("Failed to execute app: %v\n", err)
			return false
		}
		return true
	}
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
