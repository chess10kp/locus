package launcher

import (
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/chess10kp/locus/internal/apps"
	"github.com/chess10kp/locus/internal/config"
	"github.com/sahilm/fuzzy"
)

type AppLauncher struct {
	config     *config.Config
	appLoader  *apps.AppLoader
	apps       []apps.App
	appsLoaded bool
	mu         sync.RWMutex
	// Pre-computed search data for performance
	appNames        []string
	nameToApp       map[string]apps.App
	initialized     bool
	frecencyTracker *FrecencyTracker
}

type AppLauncherFactory struct{}

func (f *AppLauncherFactory) Name() string {
	return "apps"
}

func (f *AppLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewAppLauncher(cfg)
}

func init() {
	RegisterLauncherFactory(&AppLauncherFactory{})
}

func NewAppLauncher(cfg *config.Config) *AppLauncher {
	return &AppLauncher{
		config:    cfg,
		appLoader: apps.NewAppLoader(cfg),
		apps:      []apps.App{},
	}
}

func (l *AppLauncher) SetFrecencyTracker(tracker *FrecencyTracker) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.frecencyTracker = tracker
}

func (l *AppLauncher) GetFrecencyTracker() *FrecencyTracker {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.frecencyTracker
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

func (l *AppLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *AppLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	populateStart := time.Now()
	log.Printf("[APP-LAUNCHER] Populate started for query='%s'", query)

	l.mu.Lock()
	defer l.mu.Unlock()

	query = strings.TrimSpace(query)
	if query == "" {
		// Return top apps by frecency score
		maxResults := l.config.Launcher.Search.MaxResults
		sortedApps := l.getAppsSortedByFrecency()
		if len(sortedApps) > maxResults {
			sortedApps = sortedApps[:maxResults]
		}
		log.Printf("[APP-LAUNCHER] Empty query, returning %d top apps by frecency", len(sortedApps))
		return l.appsToItems(sortedApps)
	}

	// Use fuzzy search with frecency ranking
	maxResults := l.config.Launcher.Search.MaxResults
	results := l.fuzzySearch(query, maxResults)
	log.Printf("[APP-LAUNCHER] Fuzzy search completed in %v, returned %d results", time.Since(populateStart), len(results))
	return results
}

func (l *AppLauncher) fuzzySearch(query string, maxResults int) []*LauncherItem {
	fuzzyStart := time.Now()
	log.Printf("[APP-LAUNCHER] Fuzzy search started for query='%s' against %d apps", query, len(l.apps))

	findStart := time.Now()
	matches := fuzzy.Find(query, l.appNames)
	log.Printf("[APP-LAUNCHER] Fuzzy find completed in %v, found %d raw matches", time.Since(findStart), len(matches))

	type scoredMatch struct {
		match fuzzy.Match
		score float64
	}

	scoredMatches := make([]scoredMatch, 0, len(matches))
	for _, match := range matches {
		frecencyScore := 0.0
		if l.frecencyTracker != nil {
			frecencyScore = l.frecencyTracker.GetFrecencyScore(match.Str)
		}

		weightedScore := float64(match.Score) + (frecencyScore * 2.0)
		scoredMatches = append(scoredMatches, scoredMatch{
			match: match,
			score: weightedScore,
		})
	}

	for i := 0; i < len(scoredMatches); i++ {
		for j := i + 1; j < len(scoredMatches); j++ {
			if scoredMatches[j].score > scoredMatches[i].score {
				scoredMatches[i], scoredMatches[j] = scoredMatches[j], scoredMatches[i]
			}
		}
	}

	items := make([]*LauncherItem, 0, min(len(scoredMatches), maxResults))
	for i := 0; i < len(scoredMatches) && i < maxResults; i++ {
		scored := scoredMatches[i]
		if app, ok := l.nameToApp[scored.match.Str]; ok {
			item := l.appToItem(app)
			log.Printf("[APP-LAUNCHER] App '%s' - fuzzy_score=%d, frecency=%.2f, total=%.2f",
				app.Name, scored.match.Score, l.frecencyTracker.GetFrecencyScore(app.Name), scored.score)
			items = append(items, item)
		}
	}

	log.Printf("[APP-LAUNCHER] Fuzzy search completed in %v, returning %d items", time.Since(fuzzyStart), len(items))
	return items
}

func (l *AppLauncher) getAppsSortedByFrecency() []apps.App {
	if l.frecencyTracker == nil {
		return l.apps
	}

	topApps := l.frecencyTracker.GetTopApps(len(l.apps))
	appMap := make(map[string]bool, len(l.apps))
	for _, app := range l.apps {
		appMap[app.Name] = true
	}

	result := make([]apps.App, 0, len(l.apps))
	usedNames := make(map[string]bool)

	for _, frecencyMatch := range topApps {
		if usedNames[frecencyMatch.AppName] {
			continue
		}
		if app, ok := l.nameToApp[frecencyMatch.AppName]; ok {
			result = append(result, app)
			usedNames[frecencyMatch.AppName] = true
		}
	}

	for _, app := range l.apps {
		if !usedNames[app.Name] {
			result = append(result, app)
		}
	}

	return result
}

func (l *AppLauncher) appToItem(app apps.App) *LauncherItem {
	icon := app.Icon
	if icon == "" {
		icon = l.config.Launcher.Icons.FallbackIcon
	}

	return &LauncherItem{
		Title:      app.Name,
		Subtitle:   app.Description,
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

func (l *AppLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
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
