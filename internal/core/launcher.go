package core

import (
	"context"
	"errors"
	"fmt"
	"log"
	"regexp"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"time"
	"unsafe"

	"github.com/chess10kp/locus/internal/config"
	"github.com/chess10kp/locus/internal/launcher"
	"github.com/chess10kp/locus/internal/layer"
	"github.com/gotk3/gotk3/gdk"
	"github.com/gotk3/gotk3/glib"
	"github.com/gotk3/gotk3/gtk"
	"github.com/gotk3/gotk3/pango"
)

var debugLogger = log.New(log.Writer(), "[LAUNCHER-DEBUG] ", log.LstdFlags|log.Lmicroseconds)

func easeOutCubic(t float64) float64 {
	return 1 - (1-t)*(1-t)*(1-t)
}

// logMemoryStats provides memory usage information for debugging
func (l *Launcher) logMemoryStats(context string) {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	log.Printf("[MEMORY-%s] Alloc=%d MB, TotalAlloc=%d MB, Sys=%d MB, NumGC=%d",
		context,
		m.Alloc/1024/1024,
		m.TotalAlloc/1024/1024,
		m.Sys/1024/1024,
		m.NumGC,
	)
}

var (
	ErrLauncherAlreadyRunning = errors.New("launcher is already running")
)

type Launcher struct {
	app                *App
	config             *config.Config
	window             *gtk.Window
	searchEntry        *gtk.Entry
	resultList         *gtk.ListBox
	gridFlowBox        *gtk.FlowBox
	registry           *launcher.LauncherRegistry
	iconCache          *launcher.IconCache
	thumbnailCache     *launcher.ThumbnailCache
	currentInput       string
	currentItems       []*launcher.LauncherItem
	scrolledWindow     *gtk.ScrolledWindow
	badgesBox          *gtk.Box
	footerBox          *gtk.Box
	footerLabel        *gtk.Label
	running            bool
	visible            atomic.Bool
	searchTimer        *time.Timer
	searchVersion      int64 // Track search version to prevent race conditions
	gridMode           bool
	colorPreviewBox    *gtk.Box
	colorPreviewWidget *gtk.Box

	mu                    sync.RWMutex
	refreshUIChan         chan launcher.RefreshUIRequest
	statusChan            chan launcher.StatusRequest
	ctx                   context.Context
	cancel                context.CancelFunc
	screen                *gdk.Screen
	display               *gdk.Display
	monitorHandler        glib.SignalHandle
	monitorDebounceSource glib.SourceHandle
	recreating            bool
}

func NewLauncher(app *App, cfg *config.Config) (*Launcher, error) {
	log.Printf("[LAUNCHER-INIT] Creating new launcher with config: window=%dx%d", cfg.Launcher.Window.Width, cfg.Launcher.Window.Height)

	window, err := gtk.WindowNew(gtk.WINDOW_TOPLEVEL)
	if err != nil {
		log.Printf("[LAUNCHER-INIT] ERROR: Failed to create GTK window: %v", err)
		return nil, fmt.Errorf("failed to create window: %w", err)
	}
	log.Printf("[LAUNCHER-INIT] GTK window created successfully")

	// Enable transparency
	log.Printf("[LAUNCHER-INIT] Setting up window transparency")
	screen, err := gdk.ScreenGetDefault()
	if err != nil {
		log.Printf("[LAUNCHER-INIT] WARNING: Could not get default screen: %v", err)
		screen = nil
	} else {
		visual, _ := screen.GetRGBAVisual()
		if visual != nil {
			window.SetVisual(visual)
			log.Printf("[LAUNCHER-INIT] Window transparency enabled")
		} else {
			log.Printf("[LAUNCHER-INIT] WARNING: Could not get RGBA visual for transparency")
		}
	}

	display, err := gdk.DisplayGetDefault()
	if err != nil {
		log.Printf("[LAUNCHER-INIT] WARNING: Could not get default display: %v", err)
		display = nil
	}

	log.Printf("[LAUNCHER-INIT] Configuring window properties")
	window.SetDecorated(false)
	window.SetSkipTaskbarHint(true)
	window.SetSkipPagerHint(true)
	window.SetResizable(false)
	window.SetName("launcher-window")
	log.Printf("[LAUNCHER-INIT] Window properties configured")

	log.Printf("[LAUNCHER-INIT] Creating main vertical box container")
	box, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 0)
	if err != nil {
		log.Printf("[LAUNCHER-INIT] ERROR: Failed to create main box: %v", err)
		return nil, fmt.Errorf("failed to create box: %w", err)
	}
	log.Printf("[LAUNCHER-INIT] Main box container created")

	box.SetVExpand(true)
	box.SetHExpand(false)
	// Add box directly to window
	window.Add(box)
	log.Printf("[LAUNCHER-INIT] Main box added to window")

	// Create footer box for context information
	log.Printf("[LAUNCHER-INIT] Creating footer box and label")
	footerBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 0)
	if err != nil {
		log.Printf("[LAUNCHER-INIT] ERROR: Failed to create footer box: %v", err)
		return nil, fmt.Errorf("failed to create footer box: %w", err)
	}
	footerBox.SetName("footer-box")

	footerLabel, err := gtk.LabelNew("Applications")
	if err != nil {
		log.Printf("[LAUNCHER-INIT] ERROR: Failed to create footer label: %v", err)
		return nil, fmt.Errorf("failed to create footer label: %w", err)
	}
	footerLabel.SetName("footer-label")
	footerBox.PackStart(footerLabel, false, false, 0)
	log.Printf("[LAUNCHER-INIT] Footer box and label created")

	box.PackStart(footerBox, false, false, 4)
	log.Printf("[LAUNCHER-INIT] Footer box packed into main box")

	log.Printf("[LAUNCHER-INIT] Creating search entry widget")
	searchEntry, err := gtk.EntryNew()
	if err != nil {
		log.Printf("[LAUNCHER-INIT] ERROR: Failed to create search entry: %v", err)
		return nil, fmt.Errorf("failed to create search entry: %w", err)
	}
	log.Printf("[LAUNCHER-INIT] Search entry created")

	searchEntry.SetPlaceholderText("Search or type a command...")
	searchEntry.SetName("launcher-entry")
	log.Printf("[LAUNCHER-INIT] Search entry configured")

	// Create horizontal box for search entry and buttons
	log.Printf("[LAUNCHER-INIT] Creating horizontal box for search entry")
	hbox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 5)
	if err != nil {
		log.Printf("[LAUNCHER-INIT] ERROR: Failed to create hbox: %v", err)
		return nil, fmt.Errorf("failed to create hbox: %w", err)
	}
	log.Printf("[LAUNCHER-INIT] Horizontal box created")
	hbox.SetHExpand(true)
	hbox.PackStart(searchEntry, true, true, 0)

	box.PackStart(hbox, false, false, 0)
	log.Printf("[LAUNCHER-INIT] Search entry packed into horizontal box")

	log.Printf("[LAUNCHER-INIT] Creating scrolled window and result list")
	scrolledWindow, err := gtk.ScrolledWindowNew(nil, nil)
	if err != nil {
		log.Printf("[LAUNCHER-INIT] ERROR: Failed to create scrolled window: %v", err)
		return nil, fmt.Errorf("failed to create scrolled window: %w", err)
	}

	scrolledWindow.SetPolicy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
	scrolledWindow.SetVExpand(true)
	scrolledWindow.SetHExpand(false)
	scrolledWindow.SetMinContentHeight(5 * 44) // Minimum height for 5 results
	scrolledWindow.SetSizeRequest(cfg.Launcher.Window.Width, -1)

	resultList, err := gtk.ListBoxNew()
	if err != nil {
		log.Printf("[LAUNCHER-INIT] ERROR: Failed to create result list: %v", err)
		return nil, fmt.Errorf("failed to create result list: %w", err)
	}

	resultList.SetName("result-list")
	resultList.SetVExpand(true)
	resultList.SetHExpand(true) // Allow horizontal expansion for scrolling
	scrolledWindow.Add(resultList)
	scrolledWindow.ShowAll()
	log.Printf("[LAUNCHER-INIT] Scrolled window and result list created")

	// Add scrolled window to the main box
	box.PackStart(scrolledWindow, true, true, 0)
	log.Printf("[LAUNCHER-INIT] Scrolled window packed into main box")

	// Create grid flow box for grid mode
	log.Printf("[LAUNCHER-INIT] Creating grid flow box")
	gridFlowBox, err := gtk.FlowBoxNew()
	if err != nil {
		log.Printf("[LAUNCHER-INIT] ERROR: Failed to create grid flow box: %v", err)
		return nil, fmt.Errorf("failed to create grid flow box: %w", err)
	}
	gridFlowBox.SetName("grid-flow-box")
	gridFlowBox.SetVExpand(true)
	gridFlowBox.SetHExpand(false)
	gridFlowBox.SetSelectionMode(gtk.SELECTION_SINGLE)
	gridFlowBox.SetHomogeneous(true)
	gridFlowBox.SetMaxChildrenPerLine(5)
	gridFlowBox.SetColumnSpacing(10)
	gridFlowBox.SetRowSpacing(10)
	// Don't show grid box initially
	gridFlowBox.Hide()
	log.Printf("[LAUNCHER-INIT] Grid flow box created and configured")

	// Create badges box for keyboard shortcuts
	log.Printf("[LAUNCHER-INIT] Creating badges box for keyboard shortcuts")
	badgesBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 8)
	if err != nil {
		log.Printf("[LAUNCHER-INIT] ERROR: Failed to create badges box: %v", err)
		return nil, fmt.Errorf("failed to create badges box: %w", err)
	}
	badgesBox.SetName("badges-box")
	badgesBox.SetHAlign(gtk.ALIGN_START)
	badgesBox.SetHExpand(false)
	badgesBox.SetSizeRequest(cfg.Launcher.Window.Width, -1)

	// Add keyboard shortcut hints
	shortcuts := []string{"Select: Return", "↓: Ctrl+J", "↑: Ctrl+K"}
	for _, shortcut := range shortcuts {
		label, err := gtk.LabelNew(shortcut)
		if err != nil {
			log.Printf("[LAUNCHER-INIT] WARNING: Failed to create badge label for '%s': %v", shortcut, err)
			continue
		}
		label.SetName("badge-label")
		badgesBox.PackStart(label, false, false, 0)
	}
	box.PackStart(badgesBox, false, false, 4)
	log.Printf("[LAUNCHER-INIT] Badges box created with %d shortcuts", len(shortcuts))

	// Create color preview box (hidden by default)
	log.Printf("[LAUNCHER-INIT] Creating color preview box")
	colorPreviewBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 8)
	if err != nil {
		log.Printf("[LAUNCHER-INIT] ERROR: Failed to create color preview box: %v", err)
		return nil, fmt.Errorf("failed to create color preview box: %w", err)
	}
	colorPreviewBox.SetName("color-preview-box")
	colorPreviewBox.SetHAlign(gtk.ALIGN_START)
	colorPreviewBox.SetMarginStart(8)
	colorPreviewBox.SetMarginEnd(8)
	colorPreviewBox.Hide()

	// Create color preview widget (box with background color)
	colorPreviewWidget, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 0)
	if err != nil {
		log.Printf("[LAUNCHER-INIT] ERROR: Failed to create color preview widget: %v", err)
		return nil, fmt.Errorf("failed to create color preview widget: %w", err)
	}
	colorPreviewWidget.SetName("color-preview-widget")
	colorPreviewWidget.SetSizeRequest(30, 30)
	colorPreviewWidget.SetMarginStart(4)
	colorPreviewWidget.SetMarginEnd(4)

	colorPreviewBox.PackStart(colorPreviewWidget, false, false, 0)
	box.PackStart(colorPreviewBox, false, false, 4)
	log.Printf("[LAUNCHER-INIT] Color preview box created and packed")

	log.Printf("[LAUNCHER-INIT] Creating launcher registry")
	registry := launcher.NewLauncherRegistry(cfg)
	log.Printf("[LAUNCHER-INIT] Launcher registry created")

	// Create icon cache
	log.Printf("[LAUNCHER-INIT] Creating icon cache")
	iconCache, err := launcher.NewIconCache(cfg)
	if err != nil {
		log.Printf("[LAUNCHER-INIT] WARNING: Failed to create icon cache: %v, continuing without cache", err)
		// Continue without cache - icons will use default GTK sizes
		iconCache = nil
	} else {
		log.Printf("[LAUNCHER-INIT] Icon cache created successfully")
	}

	// Create thumbnail cache for grid items - DISABLED to prevent image corruption
	log.Printf("[LAUNCHER-INIT] Thumbnail cache disabled to prevent image corruption")
	var thumbnailCache *launcher.ThumbnailCache = nil

	// Create channels for hook context
	log.Printf("[LAUNCHER-INIT] Creating communication channels")
	refreshUIChan := make(chan launcher.RefreshUIRequest, 1)
	statusChan := make(chan launcher.StatusRequest, 10) // Buffer for multiple status messages
	ctx, cancel := context.WithCancel(context.Background())
	log.Printf("[LAUNCHER-INIT] Communication channels created")

	log.Printf("[LAUNCHER-INIT] Creating launcher struct with all components")
	l := &Launcher{
		app:                app,
		config:             cfg,
		window:             window,
		searchEntry:        searchEntry,
		resultList:         resultList,
		gridFlowBox:        gridFlowBox,
		scrolledWindow:     scrolledWindow,
		badgesBox:          badgesBox,
		footerBox:          footerBox,
		footerLabel:        footerLabel,
		registry:           registry,
		iconCache:          iconCache,
		thumbnailCache:     thumbnailCache,
		colorPreviewBox:    colorPreviewBox,
		colorPreviewWidget: colorPreviewWidget,
		refreshUIChan:      refreshUIChan,
		statusChan:         statusChan,
		ctx:                ctx,
		cancel:             cancel,
		screen:             screen,
		display:            display,
	}
	log.Printf("[LAUNCHER-INIT] Launcher struct created")

	// Start goroutines to handle channel requests
	log.Printf("[LAUNCHER-INIT] Starting background goroutines")
	go l.handleRefreshUIRequests(ctx, refreshUIChan)
	go l.handleStatusRequests(ctx, statusChan)
	log.Printf("[LAUNCHER-INIT] Background goroutines started")

	// Setup launcher-specific styles
	log.Printf("[LAUNCHER-INIT] Setting up launcher styles")
	SetupLauncherStyles(l.config)
	log.Printf("[LAUNCHER-INIT] Launcher styles set up")

	log.Printf("[LAUNCHER-INIT] Setting up GTK signal handlers")
	l.setupSignals()
	log.Printf("[LAUNCHER-INIT] GTK signal handlers set up")

	log.Printf("[LAUNCHER-INIT] Launcher initialization completed successfully")
	return l, nil
}

func (l *Launcher) setupSignals() {
	if l == nil || l.searchEntry == nil || l.resultList == nil || l.window == nil {
		log.Printf("[LAUNCHER] Cannot setup signals - launcher or widgets are nil")
		return
	}

	l.searchEntry.Connect("changed", func() {
		defer func() {
			if r := recover(); r != nil {
				log.Printf("[LAUNCHER] Panic recovered in search changed: %v", r)
			}
		}()
		if l == nil || l.searchEntry == nil {
			return
		}
		text, _ := l.searchEntry.GetText()
		l.onSearchChanged(text)
	})

	l.searchEntry.Connect("activate", func() {
		defer func() {
			if r := recover(); r != nil {
				log.Printf("[LAUNCHER] Panic recovered in search activate: %v", r)
			}
		}()
		if l == nil {
			return
		}
		l.onActivate()
	})

	l.searchEntry.Connect("key-press-event", func(entry *gtk.Entry, event *gdk.Event) bool {
		defer func() {
			if r := recover(); r != nil {
				log.Printf("[LAUNCHER] Panic recovered in key press: %v", r)
			}
		}()
		if event == nil {
			return false
		}
		if l == nil || l.searchEntry == nil {
			return false
		}
		if !l.visible.Load() {
			return false
		}
		keyEvent := gdk.EventKeyNewFromEvent(event)
		if keyEvent == nil {
			return false
		}
		return l.onKeyPress(keyEvent)
	})

	l.resultList.Connect("row-activated", func(list *gtk.ListBox, row *gtk.ListBoxRow) {
		defer func() {
			if r := recover(); r != nil {
				log.Printf("[LAUNCHER] Panic recovered in row activated: %v", r)
			}
		}()
		if l == nil {
			return
		}
		if row == nil {
			return
		}
		l.onRowActivated(row)
	})

	l.gridFlowBox.Connect("child-activated", func(box *gtk.FlowBox, child *gtk.FlowBoxChild) {
		defer func() {
			if r := recover(); r != nil {
				log.Printf("[LAUNCHER] Panic recovered in grid child activated: %v", r)
			}
		}()
		if l == nil {
			return
		}
		if child == nil {
			return
		}
		l.onGridChildActivated(child)
	})

	l.gridFlowBox.Connect("selected-children-changed", func(box *gtk.FlowBox) {
		defer func() {
			if r := recover(); r != nil {
				log.Printf("[LAUNCHER] Panic recovered in grid selection changed: %v", r)
			}
		}()
		if l == nil {
			return
		}
		l.onGridSelectionChanged()
	})
}

func (l *Launcher) onGridChildActivated(child *gtk.FlowBoxChild) {
	if l == nil || child == nil {
		return
	}

	// Get index of the activated child
	index := child.GetIndex()
	if index < 0 || index >= len(l.currentItems) {
		return
	}

	item := l.currentItems[index]

	// Execute hooks first
	if l.registry != nil {
		hookCtx := l.createHookContext(item)
		if hookCtx != nil && l.ctx != nil {
			hookRegistry := l.registry.GetHookRegistry()
			if hookRegistry != nil {
				result := hookRegistry.ExecuteSelectHooks(l.ctx, hookCtx, item.ActionData)
				if result.Handled {
					log.Printf("[LAUNCHER] Hook handled action, hiding launcher")
					l.Hide()
					return
				}
			}
		}
	}

	// Fall back to default execution
	if l.registry != nil {
		if err := l.registry.Execute(item); err != nil {
			log.Printf("[LAUNCHER] Failed to execute item: %v\n", err)
		}
	}

	l.Hide()
}

func (l *Launcher) onGridSelectionChanged() {
	if l == nil {
		return
	}

	// Check if wallpaper preview is enabled
	if !l.config.Launcher.Wallpaper.PreviewOnNav {
		return
	}

	l.mu.RLock()
	defer l.mu.RUnlock()

	// Get selected child from grid
	selected := l.gridFlowBox.GetSelectedChildren()
	if len(selected) == 0 {
		return
	}

	// Get the selected item
	child := selected[0]
	if child == nil {
		return
	}

	index := child.GetIndex()
	if index < 0 || index >= len(l.currentItems) {
		return
	}

	item := l.currentItems[index]

	// Call preview action if available
	if item.PreviewAction != nil {
		go func() {
			if err := item.PreviewAction(); err != nil {
				log.Printf("[LAUNCHER] Preview action failed: %v", err)
			}
		}()
	}
}

func (l *Launcher) onSearchChanged(text string) {
	searchStart := time.Now()
	defer func() {
		duration := time.Since(searchStart)
		if duration > 500*time.Millisecond {
			log.Printf("[LAUNCHER-SEARCH] WARNING: onSearchChanged took %v for query: '%s'", duration, text)
		} else {
			log.Printf("[LAUNCHER-SEARCH] onSearchChanged completed in %v for query: '%s'", duration, text)
		}
	}()

	log.Printf("[LAUNCHER-SEARCH] Search input changed to: '%s' (length: %d)", text, len(text))

	l.mu.Lock()
	defer l.mu.Unlock()

	l.currentInput = text

	// Update footer based on launcher context
	log.Printf("[LAUNCHER-SEARCH] Updating footer for input: '%s'", text)
	l.updateFooter(text)

	// Update color preview if input is a color
	log.Printf("[LAUNCHER-SEARCH] Updating color preview for input: '%s'", text)
	l.updateColorPreview(text)

	// Increment search version for this request
	version := atomic.AddInt64(&l.searchVersion, 1)
	searchVersion := version // Copy for closure

	// Calculate adaptive debounce delay
	baseDelay := l.config.Launcher.Search.DebounceDelay
	var debounceMs int

	switch {
	case len(text) == 0:
		debounceMs = 0 // Immediate for empty
	case len(text) == 1:
		debounceMs = 50 // Very fast for single char
	case len(text) <= 3:
		debounceMs = 100 // Fast for short queries (user-approved)
	default:
		debounceMs = baseDelay // Standard delay (150ms default)
	}

	log.Printf("[LAUNCHER-SEARCH] Using debounce delay: %dms (base: %dms) for query: '%s'", debounceMs, baseDelay, text)

	// Cancel previous timer if exists
	if l.searchTimer != nil {
		log.Printf("[LAUNCHER-SEARCH] Cancelling previous search timer")
		l.stopAndDrainSearchTimer()
	}

	// Start new timer with adaptive debounce delay
	log.Printf("[LAUNCHER-SEARCH] Starting new search timer with %dms delay, version: %d", debounceMs, version)
	l.searchTimer = time.AfterFunc(time.Duration(debounceMs)*time.Millisecond, func() {
		log.Printf("[LAUNCHER-SEARCH] Search timer fired for query: '%s', version: %d", text, version)

		// Check if this timer callback is still valid before proceeding
		currentVersion := atomic.LoadInt64(&l.searchVersion)
		if version != currentVersion {
			log.Printf("[LAUNCHER-SEARCH] Search cancelled - version mismatch (expected: %d, current: %d)", version, currentVersion)
			return
		}

		// Run search in a goroutine to avoid blocking UI
		go func(query string, version int64, startTime time.Time) {
			searchGoroutineStart := time.Now()
			defer func() {
				if r := recover(); r != nil {
					log.Printf("[LAUNCHER-SEARCH-PANIC] Recovered from panic in search goroutine: %v", r)
				}
			}()

			log.Printf("[LAUNCHER-SEARCH] Starting registry search for query: '%s', version: %d", query, version)

			// Double-check version before expensive search operation
			currentVersion = atomic.LoadInt64(&l.searchVersion)
			if version != currentVersion {
				log.Printf("[LAUNCHER-SEARCH] Registry search cancelled - version mismatch (expected: %d, current: %d)", version, currentVersion)
				return
			}

			items, err := l.registry.Search(query)
			if err != nil {
				log.Printf("[LAUNCHER-SEARCH] ERROR: Registry search failed for query '%s': %v", query, err)
				return
			}

			searchDuration := time.Since(searchGoroutineStart)
			log.Printf("[LAUNCHER-SEARCH] Registry search completed in %v, found %d items for query: '%s'", searchDuration, len(items), query)

			// Update UI in main thread using IdleAdd
			glib.IdleAdd(func() bool {
				uiUpdateStart := time.Now()
				// Get current version atomically to avoid race conditions
				currentVersion := atomic.LoadInt64(&l.searchVersion)

				// Skip stale results from older searches
				if version != currentVersion {
					log.Printf("[LAUNCHER-SEARCH] UI update skipped - stale results (expected version: %d, current: %d)", version, currentVersion)
					return false
				}

				log.Printf("[LAUNCHER-SEARCH] Updating UI with %d search results for version: %d", len(items), version)
				l.updateResults(items, version)

				uiUpdateDuration := time.Since(uiUpdateStart)
				log.Printf("[LAUNCHER-SEARCH] UI update completed in %v for %d items", uiUpdateDuration, len(items))

				return false // Don't repeat
			})
		}(text, searchVersion, searchStart)
	})

	// For zero delay (empty string), also trigger immediate update
	if debounceMs == 0 {
	}
}

func (l *Launcher) updateResults(items []*launcher.LauncherItem, version int64) {
	startTime := time.Now()
	defer func() {
		duration := time.Since(startTime)
		if duration > 500*time.Millisecond {
			log.Printf("[LAUNCHER-UI] WARNING: updateResults took %v for %d items (version: %d)", duration, len(items), version)
		} else {
			log.Printf("[LAUNCHER-UI] updateResults completed in %v for %d items (version: %d)", duration, len(items), version)
		}
	}()

	log.Printf("[LAUNCHER-UI] Starting UI update with %d items (version: %d)", len(items), version)

	// Check if widgets are still valid
	if l.resultList == nil || l.window == nil {
		log.Printf("[LAUNCHER-UI] ERROR: Widgets are nil - resultList: %v, window: %v", l.resultList == nil, l.window == nil)
		return
	}

	l.mu.Lock()
	defer l.mu.Unlock()
	l.updateResultsUnsafe(items, version)
}

func (l *Launcher) updateResultsUnsafe(items []*launcher.LauncherItem, version int64) bool {
	log.Printf("[LAUNCHER-UI] updateResultsUnsafe called with %d items (version: %d)", len(items), version)

	// Check if resultList is still valid
	if l.resultList == nil {
		log.Printf("[LAUNCHER-UI] ERROR: resultList is nil")
		return false
	}

	// Double-check version is still current
	currentVersion := atomic.LoadInt64(&l.searchVersion)
	if version != currentVersion {
		log.Printf("[LAUNCHER-UI] Skipping stale update - version mismatch (expected: %d, current: %d)", version, currentVersion)
		return false // Skip stale update
	}

	l.currentItems = items

	// Check if we should use grid mode
	shouldUseGridMode := false
	var gridConfig *launcher.GridConfig

	log.Printf("[LAUNCHER-UI] Checking grid mode for %d items", len(items))

	// Determine if any launcher requests grid mode
	for i, item := range items {
		if item.Launcher != nil && item.Launcher.GetSizeMode() == launcher.LauncherSizeModeGrid {
			shouldUseGridMode = true
			gridConfig = item.Launcher.GetGridConfig()
			log.Printf("[LAUNCHER-UI] Grid mode enabled by item %d (launcher: %s)", i, item.Launcher.Name())
			break
		}
	}

	// Explicitly disable grid mode for HelpLauncher items
	// HelpLauncher creates items that reference other launchers, which can incorrectly trigger grid mode
	if len(items) > 0 && items[0].Launcher != nil && items[0].Launcher.Name() == "help" {
		log.Printf("[LAUNCHER-UI] Disabling grid mode for HelpLauncher")
		shouldUseGridMode = false
		gridConfig = nil
	}

	log.Printf("[LAUNCHER-UI] Grid mode decision: shouldUseGridMode=%v, current gridMode=%v", shouldUseGridMode, l.gridMode)

	// Switch between list and grid mode
	if shouldUseGridMode != l.gridMode {
		log.Printf("[LAUNCHER-UI] Switching view mode to grid=%v", shouldUseGridMode)
		l.switchViewMode(shouldUseGridMode, gridConfig)
	}

	if l.gridMode {
		log.Printf("[LAUNCHER-UI] Updating grid results")
		l.updateGridResults(items)
	} else {
		log.Printf("[LAUNCHER-UI] Updating list results")
		l.updateListResults(items)
	}

	log.Printf("[LAUNCHER-UI] updateResultsUnsafe completed successfully")
	return true
}

func (l *Launcher) updateListResults(items []*launcher.LauncherItem) {
	log.Printf("[LAUNCHER-LIST] updateListResults called with %d items", len(items))

	// Remove all rows by repeatedly removing the first row
	removedCount := 0
	for {
		row := l.resultList.GetRowAtIndex(0)
		if row == nil {
			break
		}
		l.resultList.Remove(row)
		removedCount++
	}
	if removedCount > 0 {
		log.Printf("[LAUNCHER-LIST] Removed %d existing rows", removedCount)
	}

	// Create new result rows
	addedCount := 0
	for i, item := range items {
		row, err := l.createResultRow(item, i)
		if err != nil {
			log.Printf("[LAUNCHER-LIST] ERROR: Failed to create row %d for item '%s': %v", i, item.Title, err)
			continue
		}
		l.resultList.Add(row)
		addedCount++
	}
	log.Printf("[LAUNCHER-LIST] Added %d new rows (%d successful)", len(items), addedCount)

	// Make sure the scrolled window is visible
	if l.scrolledWindow != nil {
		log.Printf("[LAUNCHER-LIST] Showing scrolled window")
		l.scrolledWindow.ShowAll()
	} else {
		log.Printf("[LAUNCHER-LIST] WARNING: Scrolled window is nil")
	}

	// Show all widgets in the list
	log.Printf("[LAUNCHER-LIST] Showing all list widgets")
	l.resultList.ShowAll()

	// Force the listbox to redraw
	log.Printf("[LAUNCHER-LIST] Queuing redraws")
	l.resultList.QueueDraw()
	if l.scrolledWindow != nil {
		l.scrolledWindow.QueueDraw()
	}

	// Select first row if any
	if len(items) > 0 {
		log.Printf("[LAUNCHER-LIST] Selecting first row")
		children := l.resultList.GetChildren()
		if children != nil && children.Length() > 0 {
			if child := children.NthData(0); child != nil {
				if row, ok := child.(*gtk.ListBoxRow); ok {
					l.resultList.SelectRow(row)
					log.Printf("[LAUNCHER-LIST] First row selected successfully")
				} else {
					log.Printf("[LAUNCHER-LIST] ERROR: First child is not a ListBoxRow")
				}
			} else {
				log.Printf("[LAUNCHER-LIST] ERROR: No children in list after update")
			}
		} else {
			log.Printf("[LAUNCHER-LIST] WARNING: No children in list after update")
		}
	} else {
		log.Printf("[LAUNCHER-LIST] No items to select")
	}

	log.Printf("[LAUNCHER-LIST] updateListResults completed")
}

func (l *Launcher) updateGridResults(items []*launcher.LauncherItem) {
	log.Printf("[LAUNCHER-GRID] updateGridResults called with %d items", len(items))

	// Remove all children from flow box
	children := l.gridFlowBox.GetChildren()
	removedCount := 0
	for i := uint(0); i < children.Length(); i++ {
		if child := children.NthData(i); child != nil {
			l.gridFlowBox.Remove(child.(gtk.IWidget))
			removedCount++
		}
	}
	if removedCount > 0 {
		log.Printf("[LAUNCHER-GRID] Removed %d existing grid children", removedCount)
	}

	// Create new grid items
	addedCount := 0
	for i, item := range items {
		gridItem, err := l.createGridItem(item, i)
		if err != nil {
			log.Printf("[LAUNCHER-GRID] ERROR: Failed to create grid item %d for item '%s': %v", i, item.Title, err)
			continue
		}
		l.gridFlowBox.Add(gridItem)
		addedCount++
	}
	log.Printf("[LAUNCHER-GRID] Added %d new grid items (%d successful)", len(items), addedCount)

	// Show all widgets in the grid
	log.Printf("[LAUNCHER-GRID] Showing all grid widgets")
	l.gridFlowBox.ShowAll()

	// Force the grid to redraw
	log.Printf("[LAUNCHER-GRID] Queuing redraws")
	l.gridFlowBox.QueueDraw()
	if l.scrolledWindow != nil {
		l.scrolledWindow.QueueDraw()
	}

	// Select first item if any
	if len(items) > 0 {
		log.Printf("[LAUNCHER-GRID] Selecting first grid item")
		children := l.gridFlowBox.GetChildren()
		if children != nil && children.Length() > 0 {
			if child := children.NthData(0); child != nil {
				if flowBoxChild, ok := child.(*gtk.FlowBoxChild); ok {
					l.gridFlowBox.SelectChild(flowBoxChild)
					log.Printf("[LAUNCHER-GRID] First grid item selected successfully")
				} else {
					log.Printf("[LAUNCHER-GRID] ERROR: First child is not a FlowBoxChild")
				}
			} else {
				log.Printf("[LAUNCHER-GRID] ERROR: No children in grid after update")
			}
		} else {
			log.Printf("[LAUNCHER-GRID] WARNING: No children in grid after update")
		}
	} else {
		log.Printf("[LAUNCHER-GRID] No items to select")
	}

	log.Printf("[LAUNCHER-GRID] updateGridResults completed")
}

func (l *Launcher) switchViewMode(toGrid bool, gridConfig *launcher.GridConfig) {
	log.Printf("[LAUNCHER-VIEW] Switching view mode: toGrid=%v (current gridMode=%v)", toGrid, l.gridMode)
	l.gridMode = toGrid

	if toGrid {
		log.Printf("[LAUNCHER-VIEW] Switching to grid mode")
		// Switch to grid mode
		l.resultList.Hide()
		l.scrolledWindow.Remove(l.resultList)
		l.scrolledWindow.Add(l.gridFlowBox)
		l.gridFlowBox.ShowAll()

		// Apply grid configuration if available
		if gridConfig != nil {
			log.Printf("[LAUNCHER-VIEW] Applying grid config: columns=%d, spacing=%d", gridConfig.Columns, gridConfig.Spacing)
			l.gridFlowBox.SetMaxChildrenPerLine(uint(gridConfig.Columns))
			l.gridFlowBox.SetColumnSpacing(uint(gridConfig.Spacing))
			l.gridFlowBox.SetRowSpacing(uint(gridConfig.Spacing))

			// Window size stays at configured default - no auto-resizing
		} else {
			log.Printf("[LAUNCHER-VIEW] No grid config provided, using defaults")
		}
	} else {
		log.Printf("[LAUNCHER-VIEW] Switching to list mode")
		// Switch to list mode
		l.gridFlowBox.Hide()
		l.scrolledWindow.Remove(l.gridFlowBox)
		l.scrolledWindow.Add(l.resultList)
		l.resultList.ShowAll()

		// Window size stays at configured default - no auto-resizing
	}

	// Queue redraw
	log.Printf("[LAUNCHER-VIEW] Queuing window redraw")
	l.window.QueueDraw()
	log.Printf("[LAUNCHER-VIEW] View mode switch completed")
}

func (l *Launcher) adjustWindowSizeForGrid(gridConfig *launcher.GridConfig, itemCount int) {
	if itemCount == 0 {
		return
	}

	// Calculate grid dimensions
	rows := (itemCount + gridConfig.Columns - 1) / gridConfig.Columns
	maxRows := 5 // Limit to 5 rows for visibility
	if rows > maxRows {
		rows = maxRows
	}

	// Calculate window size
	width := gridConfig.Columns*(gridConfig.ItemWidth+gridConfig.Spacing) + 40 // +40 for margins
	height := rows*(gridConfig.ItemHeight+gridConfig.Spacing) + 100            // +100 for search and footer

	l.window.SetDefaultSize(width, height)
	log.Printf("[GRID] Adjusted window size to %dx%d for grid mode", width, height)
}

func (l *Launcher) restoreDefaultWindowSize() {
	width := l.config.Launcher.Window.Width
	height := l.config.Launcher.Window.Height

	if width <= 0 {
		width = 600
	}
	if height <= 0 {
		minHeightForResults := 5 * 44
		searchEntryHeight := 50
		extraPadding := 20
		height = minHeightForResults + searchEntryHeight + extraPadding
		if height < 500 {
			height = 500
		}
	}

	l.window.SetDefaultSize(width, height)
	log.Printf("[GRID] Restored default window size to %dx%d", width, height)
}

func (l *Launcher) createResultRow(item *launcher.LauncherItem, index int) (*gtk.ListBoxRow, error) {
	row, err := gtk.ListBoxRowNew()
	if err != nil {
		return nil, err
	}

	if row == nil {
		return nil, fmt.Errorf("failed to create listbox row")
	}

	row.SetName("list-row")
	row.SetHExpand(true) // Allow row to expand horizontally for scrolling
	row.SetVAlign(gtk.ALIGN_START)

	box, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 4)
	if err != nil {
		return nil, err
	}

	box.SetMarginStart(8)
	box.SetMarginEnd(8)
	box.SetMarginTop(8)
	box.SetMarginBottom(8)
	box.SetHExpand(true) // Allow content to expand horizontally

	// Create a horizontal box for icon and text
	iconTextBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 12)
	if err != nil {
		return nil, err
	}
	iconTextBox.SetHAlign(gtk.ALIGN_START)

	// Check if item has color metadata to create a colored icon
	itemColor := ""
	if item.Metadata != nil {
		if c, ok := item.Metadata["color"]; ok {
			itemColor = c
		}
	}

	log.Printf("[LAUNCHER-ROW] Creating icon for item '%s': icon='%s', showIcon=%v, itemColor='%s'",
		item.Title, item.Icon, l.shouldShowIcon(item), itemColor)

	if item.Icon != "" && l.shouldShowIcon(item) {
		icon, err := gtk.ImageNew()
		if err != nil {
			log.Printf("[LAUNCHER-ROW] ERROR: Failed to create GTK image widget: %v", err)
			return nil, err
		}

		// Always use consistent icon size
		iconSize := l.config.Launcher.Icons.IconSize
		if iconSize <= 0 {
			iconSize = 32 // Default consistent size
		}

		log.Printf("[LAUNCHER-ROW] Loading icon '%s' at size %dx%d", item.Icon, iconSize, iconSize)

		// If item has a color, create a colored icon
		if itemColor != "" {
			log.Printf("[LAUNCHER-ROW] Creating colored icon with color '%s'", itemColor)
			pixbuf, pixErr := gdk.PixbufNew(gdk.COLORSPACE_RGB, true, 8, iconSize, iconSize)
			if pixErr == nil && pixbuf != nil {
				// Parse hex color and fill pixbuf
				if colorRGBA, ok := parseHexColor(itemColor); ok {
					log.Printf("[LAUNCHER-ROW] Successfully parsed color '%s' to RGBA: %x", itemColor, colorRGBA)
					pixbuf.Fill(colorRGBA)
					icon.SetFromPixbuf(pixbuf)
					log.Printf("[LAUNCHER-ROW] Colored icon created successfully")
				} else {
					log.Printf("[LAUNCHER-ROW] WARNING: Failed to parse color '%s', using transparent icon", itemColor)
					pixbuf.Fill(0x00000000)
					icon.SetFromPixbuf(pixbuf)
				}
			} else {
				log.Printf("[LAUNCHER-ROW] ERROR: Failed to create pixbuf for colored icon: %v", pixErr)
				icon.SetFromIconName(item.Icon, gtk.ICON_SIZE_LARGE_TOOLBAR)
			}
		} else {
			// Load standard icon
			var pixbuf *gdk.Pixbuf
			var loadErr error

			if l.iconCache != nil {
				log.Printf("[LAUNCHER-ROW] Loading icon from cache")
				// Use cache if available (includes fallback handling)
				pixbuf, loadErr = l.iconCache.GetIcon(item.Icon, iconSize)
				if loadErr != nil {
					log.Printf("[LAUNCHER-ROW] ERROR: Icon cache load failed: %v", loadErr)
				} else if pixbuf != nil {
					log.Printf("[LAUNCHER-ROW] Icon loaded from cache successfully")
				}
			} else {
				log.Printf("[LAUNCHER-ROW] Loading icon directly from theme")
				// Load directly from theme at custom size with fallback
				theme, themeErr := gtk.IconThemeGetDefault()
				if themeErr == nil {
					log.Printf("[LAUNCHER-ROW] Trying to load icon '%s' from theme", item.Icon)
					// Try the requested icon first
					pixbuf, loadErr = theme.LoadIcon(item.Icon, iconSize, gtk.ICON_LOOKUP_USE_BUILTIN)
					if loadErr != nil || pixbuf == nil {
						log.Printf("[LAUNCHER-ROW] Primary icon load failed, trying fallback")
						// Try fallback icon
						fallback := l.config.Launcher.Icons.FallbackIcon
						if fallback == "" {
							fallback = "image-missing"
						}
						if item.Icon != fallback {
							pixbuf, loadErr = theme.LoadIcon(fallback, iconSize, gtk.ICON_LOOKUP_USE_BUILTIN)
							if loadErr != nil {
								log.Printf("[LAUNCHER-ROW] Fallback icon load failed: %v", loadErr)
							}
						}
					}
				} else {
					log.Printf("[LAUNCHER-ROW] ERROR: Could not get default icon theme: %v", themeErr)
				}
			}

			if loadErr == nil && pixbuf != nil {
				log.Printf("[LAUNCHER-ROW] Icon loaded successfully, checking size: %dx%d", pixbuf.GetWidth(), pixbuf.GetHeight())
				// Ensure pixbuf is exactly the right size
				if pixbuf.GetWidth() != iconSize || pixbuf.GetHeight() != iconSize {
					log.Printf("[LAUNCHER-ROW] Scaling icon from %dx%d to %dx%d", pixbuf.GetWidth(), pixbuf.GetHeight(), iconSize, iconSize)
					// Scale to exact size if needed
					scaled, scaleErr := pixbuf.ScaleSimple(iconSize, iconSize, gdk.INTERP_BILINEAR)
					if scaleErr == nil && scaled != nil {
						pixbuf = scaled
						log.Printf("[LAUNCHER-ROW] Icon scaling successful")
					} else {
						log.Printf("[LAUNCHER-ROW] WARNING: Icon scaling failed: %v", scaleErr)
					}
				}
				icon.SetFromPixbuf(pixbuf)
				log.Printf("[LAUNCHER-ROW] Icon set from pixbuf")
			} else {
				log.Printf("[LAUNCHER-ROW] Icon loading failed, creating blank placeholder")
				// Create a blank icon at the custom size to ensure consistency
				// This ensures all icons have the same dimensions even when loading fails
				pixbuf, loadErr = gdk.PixbufNew(gdk.COLORSPACE_RGB, true, 8, iconSize, iconSize)
				if loadErr == nil && pixbuf != nil {
					// Fill with transparent background
					pixbuf.Fill(0x00000000) // RGBA: transparent
					icon.SetFromPixbuf(pixbuf)
					log.Printf("[LAUNCHER-ROW] Blank placeholder icon created")
				} else {
					log.Printf("[LAUNCHER-ROW] ERROR: Failed to create blank icon: %v", loadErr)
					// Ultimate fallback
					icon.SetFromIconName(item.Icon, gtk.ICON_SIZE_LARGE_TOOLBAR)
					log.Printf("[LAUNCHER-ROW] Using ultimate fallback icon")
				}
			}
		}

		iconTextBox.PackStart(icon, false, false, 0)
		icon.SetVAlign(gtk.ALIGN_START)
		icon.Show()
		log.Printf("[LAUNCHER-ROW] Icon added to row successfully")
	} else {
		log.Printf("[LAUNCHER-ROW] Skipping icon for item '%s' (icon empty or should not show)", item.Title)
	}

	// Create a vertical box for title and subtitle
	textBox, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 2)
	if err != nil {
		return nil, err
	}
	textBox.SetHAlign(gtk.ALIGN_START)
	textBox.SetVAlign(gtk.ALIGN_START)
	textBox.SetHExpand(false)
	iconTextBox.PackStart(textBox, true, false, 0)

	box.PackStart(iconTextBox, false, false, 0)

	label, err := gtk.LabelNew(item.Title)
	if err != nil {
		return nil, err
	}

	label.SetHAlign(gtk.ALIGN_START)
	label.SetHExpand(false)
	label.SetMaxWidthChars(30)
	label.SetEllipsize(pango.ELLIPSIZE_END)
	label.SetName("result-title")
	textBox.PackStart(label, false, false, 0)
	label.Show()

	if item.Subtitle != "" {
		subtitle := item.Subtitle
		if len(subtitle) > 50 {
			subtitle = subtitle[:50]
		}
		subLabel, err := gtk.LabelNew(subtitle)
		if err != nil {
			return nil, err
		}

		subLabel.SetHAlign(gtk.ALIGN_START)
		subLabel.SetMaxWidthChars(30)
		subLabel.SetEllipsize(pango.ELLIPSIZE_END)
		subLabel.SetOpacity(0.6)
		subLabel.SetName("result-subtitle")
		textBox.PackStart(subLabel, false, false, 0)
		subLabel.Show()
	}
	textBox.SetHExpand(false)
	textBox.Show()
	iconTextBox.SetHAlign(gtk.ALIGN_START)
	iconTextBox.SetVAlign(gtk.ALIGN_START)
	iconTextBox.SetHExpand(false)
	iconTextBox.Show()

	if index < 9 {
		hintLabel, err := gtk.LabelNew(fmt.Sprintf("%d", index+1))
		if err != nil {
			return nil, err
		}

		hintLabel.SetHAlign(gtk.ALIGN_END)
		hintLabel.SetMarginStart(8)
		box.PackEnd(hintLabel, false, false, 0)
		hintLabel.Show()
	}

	row.Add(box)
	row.ShowAll()
	return row, nil
}

func (l *Launcher) createGridItem(item *launcher.LauncherItem, index int) (gtk.IWidget, error) {
	// Get grid config from launcher
	var gridConfig *launcher.GridConfig
	if item.Launcher != nil {
		gridConfig = item.Launcher.GetGridConfig()
	}

	// Use defaults if no grid config
	if gridConfig == nil {
		gridConfig = &launcher.GridConfig{
			Columns:          5,
			ItemWidth:        200,
			ItemHeight:       150,
			Spacing:          10,
			ShowMetadata:     false,
			MetadataPosition: launcher.MetadataPositionHidden,
			AspectRatio:      launcher.AspectRatioOriginal,
		}
	}

	if item.IsSeparator {
		separatorBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 0)
		if err != nil {
			return nil, err
		}
		separatorBox.SetName("grid-separator")

		separator, err := gtk.SeparatorNew(gtk.ORIENTATION_HORIZONTAL)
		if err != nil {
			return nil, err
		}
		separatorBox.PackStart(separator, true, true, 0)

		label, err := gtk.LabelNew(item.Title)
		if err != nil {
			return nil, err
		}
		label.SetName("grid-separator-label")
		label.SetMarginStart(10)
		label.SetMarginEnd(10)
		separatorBox.PackStart(label, false, false, 0)

		separator, err = gtk.SeparatorNew(gtk.ORIENTATION_HORIZONTAL)
		if err != nil {
			return nil, err
		}
		separatorBox.PackStart(separator, true, true, 0)

		separatorBox.ShowAll()
		return separatorBox, nil
	}

	// Create container for grid item
	container, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 0)
	if err != nil {
		return nil, err
	}
	container.SetName("grid-item-container")

	// Load image if path is provided
	if item.ImagePath != "" {
		log.Printf("[LAUNCHER-GRID] Loading image for item '%s': path='%s', size=%dx%d",
			item.Title, item.ImagePath, gridConfig.ItemWidth, gridConfig.ItemHeight)

		image, err := gtk.ImageNew()
		if err != nil {
			log.Printf("[LAUNCHER-GRID] ERROR: Failed to create GTK image widget: %v", err)
			return nil, err
		}

		// Check cache first
		cacheKey := fmt.Sprintf("%s_%dx%d", item.ImagePath, gridConfig.ItemWidth, gridConfig.ItemHeight)
		var pixbuf *gdk.Pixbuf

		if l.thumbnailCache != nil {
			log.Printf("[LAUNCHER-GRID] Checking thumbnail cache for key '%s'", cacheKey)
			// Try memory cache
			if cachedData, found := l.thumbnailCache.Get(cacheKey); found {
				log.Printf("[LAUNCHER-GRID] Cache hit, loading from cache")
				pixbuf, err = gdk.PixbufNewFromData(cachedData, gdk.COLORSPACE_RGB, true, 8, gridConfig.ItemWidth, gridConfig.ItemHeight, gridConfig.ItemWidth*4)
				if err != nil {
					log.Printf("[LAUNCHER-GRID] ERROR: Failed to load pixbuf from cache: %v", err)
				} else {
					log.Printf("[LAUNCHER-GRID] Successfully loaded image from cache")
				}
			} else {
				log.Printf("[LAUNCHER-GRID] Cache miss")
			}
		} else {
			log.Printf("[LAUNCHER-GRID] No thumbnail cache available")
		}

		// Load from file if not in cache
		if pixbuf == nil {
			log.Printf("[LAUNCHER-GRID] Loading image from file: %s", item.ImagePath)
			pixbuf, err = gdk.PixbufNewFromFileAtScale(item.ImagePath, gridConfig.ItemWidth, gridConfig.ItemHeight, false)
			if err != nil {
				log.Printf("[LAUNCHER-GRID] ERROR: Failed to load image %s: %v", item.ImagePath, err)
				// Create a placeholder
				log.Printf("[LAUNCHER-GRID] Creating placeholder image")
				pixbuf, err = gdk.PixbufNew(gdk.COLORSPACE_RGB, true, 8, gridConfig.ItemWidth, gridConfig.ItemHeight)
				if err == nil {
					pixbuf.Fill(0x22222222) // Dark gray placeholder
					log.Printf("[LAUNCHER-GRID] Placeholder image created")
				} else {
					log.Printf("[LAUNCHER-GRID] ERROR: Failed to create placeholder: %v", err)
				}
			} else {
				log.Printf("[LAUNCHER-GRID] Successfully loaded image from file")
				// Cache the loaded pixbuf
				if l.thumbnailCache != nil {
					pixels := pixbuf.GetPixels()
					if len(pixels) > 0 {
						data := make([]byte, len(pixels))
						copy(data, pixels)
						l.thumbnailCache.Put(cacheKey, data)
						log.Printf("[LAUNCHER-GRID] Image cached with key '%s'", cacheKey)
					}
				}
			}
		}

		if pixbuf != nil {
			image.SetFromPixbuf(pixbuf)
			log.Printf("[LAUNCHER-GRID] Image set from pixbuf")
		} else {
			log.Printf("[LAUNCHER-GRID] WARNING: No pixbuf available for image")
		}
		container.PackStart(image, true, true, 0)
		image.Show()
		log.Printf("[LAUNCHER-GRID] Image added to grid item")
	} else {
		log.Printf("[LAUNCHER-GRID] No image path provided for item '%s'", item.Title)

		if item.Icon != "" && l.iconCache != nil {
			log.Printf("[LAUNCHER-GRID] Loading icon for item '%s': icon='%s', size=%d",
				item.Title, item.Icon, gridConfig.ItemHeight)

			pixbuf, err := l.iconCache.GetIcon(item.Icon, gridConfig.ItemHeight)
			if err != nil {
				log.Printf("[LAUNCHER-GRID] ERROR: Failed to load icon '%s': %v", item.Icon, err)
			} else {
				centerBox, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 0)
				if err != nil {
					return nil, err
				}
				centerBox.SetVAlign(gtk.ALIGN_CENTER)
				centerBox.SetHAlign(gtk.ALIGN_CENTER)

				iconImage, err := gtk.ImageNew()
				if err != nil {
					return nil, err
				}
				iconImage.SetFromPixbuf(pixbuf)
				iconImage.SetVAlign(gtk.ALIGN_CENTER)
				iconImage.SetHAlign(gtk.ALIGN_CENTER)

				centerBox.PackStart(iconImage, true, true, 0)
				container.PackStart(centerBox, true, true, 0)
				centerBox.ShowAll()
				log.Printf("[LAUNCHER-GRID] Icon added to grid item")
			}
		}
	}

	// Add metadata if configured
	if gridConfig.ShowMetadata && gridConfig.MetadataPosition != launcher.MetadataPositionHidden {
		metaBox, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 2)
		if err != nil {
			return nil, err
		}
		metaBox.SetMarginStart(4)
		metaBox.SetMarginEnd(4)
		metaBox.SetMarginTop(4)
		metaBox.SetMarginBottom(4)

		if item.Title != "" {
			titleLabel, err := gtk.LabelNew(item.Title)
			if err != nil {
				return nil, err
			}
			titleLabel.SetName("grid-item-title")
			titleLabel.SetHAlign(gtk.ALIGN_START)
			titleLabel.SetMaxWidthChars(20)
			titleLabel.SetEllipsize(pango.ELLIPSIZE_END)
			metaBox.PackStart(titleLabel, false, false, 0)
			titleLabel.Show()
		}

		if item.Subtitle != "" && gridConfig.MetadataPosition == launcher.MetadataPositionBottom {
			subtitle := item.Subtitle
			if len(subtitle) > 50 {
				subtitle = subtitle[:50]
			}
			subLabel, err := gtk.LabelNew(subtitle)
			if err != nil {
				return nil, err
			}
			subLabel.SetName("grid-item-subtitle")
			subLabel.SetHAlign(gtk.ALIGN_START)
			subLabel.SetMaxWidthChars(20)
			subLabel.SetEllipsize(pango.ELLIPSIZE_END)
			metaBox.PackStart(subLabel, false, false, 0)
			subLabel.Show()
		}

		container.PackEnd(metaBox, false, false, 0)
		metaBox.Show()
	}

	// Add keyboard shortcut hint
	if index < 9 {
		hintBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 0)
		if err != nil {
			return nil, err
		}
		hintBox.SetHAlign(gtk.ALIGN_END)
		hintBox.SetMarginStart(4)
		hintBox.SetMarginEnd(4)
		hintBox.SetMarginTop(4)

		hintLabel, err := gtk.LabelNew(fmt.Sprintf("%d", index+1))
		if err != nil {
			return nil, err
		}
		hintLabel.SetName("grid-item-hint")
		hintLabel.SetMarginTop(2)
		hintLabel.SetMarginBottom(2)
		hintLabel.SetMarginStart(4)
		hintLabel.SetMarginEnd(4)
		hintBox.PackEnd(hintLabel, false, false, 0)

		// Overlay hint on top of image if configured
		if gridConfig.MetadataPosition == launcher.MetadataPositionOverlay {
			// TODO: Implement overlay positioning
		}

		container.PackEnd(hintBox, false, false, 0)
		hintBox.Show()
		hintLabel.Show()
	}

	container.ShowAll()
	return container, nil
}

func (l *Launcher) onActivate() {
	text, _ := l.searchEntry.GetText()
	log.Printf("[LAUNCHER-ACTIVATE] onActivate called with text: '%s'", text)

	// Execute enter hooks first
	log.Printf("[LAUNCHER-ACTIVATE] Creating hook context for enter hooks")
	hookCtx := l.createHookContext(nil)
	if hookCtx == nil {
		log.Printf("[LAUNCHER-ACTIVATE] ERROR: Failed to create hook context")
	} else {
		log.Printf("[LAUNCHER-ACTIVATE] Executing enter hooks for text: '%s'", text)
		result := l.registry.GetHookRegistry().ExecuteEnterHooks(l.ctx, hookCtx, text)
		log.Printf("[LAUNCHER-ACTIVATE] Enter hooks result: handled=%v", result.Handled)

		if result.Handled {
			log.Printf("[LAUNCHER-ACTIVATE] Enter hooks handled activation, hiding launcher")
			l.Hide()
			return
		}
	}

	// Fall back to executing selected item, or first item if none selected
	selected := l.resultList.GetSelectedRow()
	if selected != nil {
		log.Printf("[LAUNCHER-ACTIVATE] Executing selected row")
		l.onRowActivated(selected)
	} else if len(l.currentItems) > 0 {
		log.Printf("[LAUNCHER-ACTIVATE] No selection, executing first item")
		item := l.currentItems[0]
		log.Printf("[LAUNCHER-ACTIVATE] First item: title='%s', launcher='%s'", item.Title, item.Launcher.Name())

		// Execute hooks first
		log.Printf("[LAUNCHER-ACTIVATE] Creating hook context for select hooks on first item")
		hookCtx := l.createHookContext(item)
		if hookCtx != nil {
			log.Printf("[LAUNCHER-ACTIVATE] Executing select hooks for first item")
			result := l.registry.GetHookRegistry().ExecuteSelectHooks(l.ctx, hookCtx, item.ActionData)
			log.Printf("[LAUNCHER-ACTIVATE] Select hooks result: handled=%v", result.Handled)
			if result.Handled {
				log.Printf("[LAUNCHER-ACTIVATE] Select hooks handled activation, hiding launcher")
				l.Hide()
				return
			}
		} else {
			log.Printf("[LAUNCHER-ACTIVATE] ERROR: Failed to create hook context for first item")
		}

		// Fall back to default execution
		log.Printf("[LAUNCHER-ACTIVATE] Executing item via registry: '%s'", item.Title)
		if l.registry != nil {
			if err := l.registry.Execute(item); err != nil {
				log.Printf("[LAUNCHER-ACTIVATE] ERROR: Failed to execute item '%s': %v", item.Title, err)
			} else {
				log.Printf("[LAUNCHER-ACTIVATE] Successfully executed item: '%s'", item.Title)
			}
		} else {
			log.Printf("[LAUNCHER-ACTIVATE] ERROR: Registry is nil, cannot execute item")
		}

		log.Printf("[LAUNCHER-ACTIVATE] Hiding launcher after execution")
		l.Hide()
	} else {
		log.Printf("[LAUNCHER-ACTIVATE] No items to execute, hiding launcher")
		l.Hide()
	}
}

func (l *Launcher) onRowActivated(row *gtk.ListBoxRow) {
	log.Printf("[LAUNCHER-ROW] onRowActivated called")
	if l == nil || row == nil {
		log.Printf("[LAUNCHER-ROW] ERROR: Launcher or row is nil")
		return
	}

	l.mu.RLock()
	index := row.GetIndex()
	log.Printf("[LAUNCHER-ROW] Row index: %d, current items count: %d", index, len(l.currentItems))
	if index < 0 || index >= len(l.currentItems) {
		log.Printf("[LAUNCHER-ROW] ERROR: Invalid row index %d (valid range: 0-%d)", index, len(l.currentItems)-1)
		l.mu.RUnlock()
		return
	}
	item := l.currentItems[index]
	l.mu.RUnlock()

	log.Printf("[LAUNCHER-ROW] Activating item: title='%s', launcher='%s', index=%d", item.Title, item.Launcher.Name(), index)

	// Execute hooks first
	if l.registry != nil {
		log.Printf("[LAUNCHER-ROW] Creating hook context for item")
		hookCtx := l.createHookContext(item)
		if hookCtx != nil && l.ctx != nil {
			hookRegistry := l.registry.GetHookRegistry()
			if hookRegistry != nil {
				log.Printf("[LAUNCHER-ROW] Executing select hooks")
				result := hookRegistry.ExecuteSelectHooks(l.ctx, hookCtx, item.ActionData)
				log.Printf("[LAUNCHER-ROW] Select hooks result: handled=%v", result.Handled)
				if result.Handled {
					log.Printf("[LAUNCHER-ROW] Hook handled action, hiding launcher")
					l.Hide()
					return
				}
			} else {
				log.Printf("[LAUNCHER-ROW] ERROR: Hook registry is nil")
			}
		} else {
			log.Printf("[LAUNCHER-ROW] ERROR: Failed to create hook context (hookCtx: %v, ctx: %v)", hookCtx == nil, l.ctx == nil)
		}
	} else {
		log.Printf("[LAUNCHER-ROW] ERROR: Registry is nil")
	}

	// Fall back to default execution
	log.Printf("[LAUNCHER-ROW] Executing item via registry")
	if l.registry != nil {
		if err := l.registry.Execute(item); err != nil {
			log.Printf("[LAUNCHER-ROW] ERROR: Failed to execute item '%s': %v", item.Title, err)
		} else {
			log.Printf("[LAUNCHER-ROW] Successfully executed item: '%s'", item.Title)
		}
	} else {
		log.Printf("[LAUNCHER-ROW] ERROR: Registry is nil, cannot execute item")
	}

	log.Printf("[LAUNCHER-ROW] Hiding launcher after row activation")
	l.Hide()
}

func (l *Launcher) onKeyPress(event *gdk.EventKey) bool {
	if event == nil {
		log.Printf("[LAUNCHER-KEY] ERROR: Key event is nil")
		return false
	}
	key := event.KeyVal()
	state := event.State()

	log.Printf("[LAUNCHER-KEY] Key press: key=%d, state=%d, visible=%v", key, state, l.visible.Load())

	if l.resultList == nil {
		log.Printf("[LAUNCHER-KEY] ERROR: Result list is nil")
		return false
	}

	switch key {
	case gdk.KEY_Escape:
		log.Printf("[LAUNCHER-KEY] Escape key pressed, hiding launcher")
		l.Hide()
		return true
	case gdk.KEY_Down:
		log.Printf("[LAUNCHER-KEY] Down arrow pressed, navigating down")
		l.navigateResult(1)
		return true
	case gdk.KEY_Up:
		log.Printf("[LAUNCHER-KEY] Up arrow pressed, navigating up")
		l.navigateResult(-1)
		return true
	case gdk.KEY_Tab:
		log.Printf("[LAUNCHER-KEY] Tab key pressed, calling onTabPressed")
		return l.onTabPressed()
	case gdk.KEY_n, gdk.KEY_j:
		if state&uint(gdk.CONTROL_MASK) != 0 {
			log.Printf("[LAUNCHER-KEY] Ctrl+N/J pressed, navigating down")
			l.navigateResult(1)
			return true
		}
		log.Printf("[LAUNCHER-KEY] N/J pressed without Ctrl, ignoring")
		return false
	case gdk.KEY_p, gdk.KEY_k: // TODO: add to config file;
		if state&uint(gdk.CONTROL_MASK) != 0 {
			log.Printf("[LAUNCHER-KEY] Ctrl+P/K pressed, navigating up")
			l.navigateResult(-1)
			return true
		}
		log.Printf("[LAUNCHER-KEY] P/K pressed without Ctrl, ignoring")
		return false
	}

	// Check for Alt+number (1-9) to directly activate corresponding entry
	if state&uint(gdk.MOD1_MASK) != 0 {
		log.Printf("[LAUNCHER-KEY] Alt modifier detected")
		var index int
		switch key {
		case gdk.KEY_1:
			index = 0
		case gdk.KEY_2:
			index = 1
		case gdk.KEY_3:
			index = 2
		case gdk.KEY_4:
			index = 3
		case gdk.KEY_5:
			index = 4
		case gdk.KEY_6:
			index = 5
		case gdk.KEY_7:
			index = 6
		case gdk.KEY_8:
			index = 7
		case gdk.KEY_9:
			index = 8
		default:
			log.Printf("[LAUNCHER-KEY] Alt pressed with non-number key: %d", key)
			return false
		}

		log.Printf("[LAUNCHER-KEY] Alt+%d pressed, activating item at index %d", index+1, index)
		l.mu.RLock()
		if index < len(l.currentItems) {
			log.Printf("[LAUNCHER-KEY] Item exists at index %d, getting row", index)
			row := l.resultList.GetRowAtIndex(index)
			if row != nil {
				l.mu.RUnlock()
				log.Printf("[LAUNCHER-KEY] Row found, activating")
				l.onRowActivated(row)
				return true
			} else {
				log.Printf("[LAUNCHER-KEY] ERROR: Row at index %d is nil", index)
			}
		} else {
			log.Printf("[LAUNCHER-KEY] No item at index %d (only %d items available)", index, len(l.currentItems))
		}
		l.mu.RUnlock()
	}

	// Check for Ctrl+number (1-9) to execute launcher-specific action on corresponding entry
	if state&uint(gdk.CONTROL_MASK) != 0 {
		log.Printf("[LAUNCHER-KEY] Ctrl modifier detected")
		var number int
		switch key {
		case gdk.KEY_1:
			number = 1
		case gdk.KEY_2:
			number = 2
		case gdk.KEY_3:
			number = 3
		case gdk.KEY_4:
			number = 4
		case gdk.KEY_5:
			number = 5
		case gdk.KEY_6:
			number = 6
		case gdk.KEY_7:
			number = 7
		case gdk.KEY_8:
			number = 8
		case gdk.KEY_9:
			number = 9
		default:
			log.Printf("[LAUNCHER-KEY] Ctrl pressed with non-number key: %d", key)
			return false
		}

		log.Printf("[LAUNCHER-KEY] Ctrl+%d pressed, executing launcher-specific action", number)
		l.mu.RLock()
		index := number - 1
		if index < len(l.currentItems) {
			item := l.currentItems[index]
			log.Printf("[LAUNCHER-KEY] Item at index %d: title='%s', launcher='%s'", index, item.Title, item.Launcher.Name())
			if item.Launcher != nil {
				action, exists := item.Launcher.GetCtrlNumberAction(number)
				if exists && action != nil {
					log.Printf("[LAUNCHER-KEY] Ctrl+%d action found, executing", number)
					l.mu.RUnlock()
					if err := action(item); err != nil {
						log.Printf("[LAUNCHER-KEY] ERROR: Ctrl+%d action failed: %v", number, err)
					} else {
						log.Printf("[LAUNCHER-KEY] Ctrl+%d action succeeded, hiding launcher", number)
						l.Hide()
					}
					return true
				} else {
					log.Printf("[LAUNCHER-KEY] No Ctrl+%d action defined for launcher '%s'", number, item.Launcher.Name())
				}
			} else {
				log.Printf("[LAUNCHER-KEY] Item has no launcher")
			}
		} else {
			log.Printf("[LAUNCHER-KEY] No item at index %d (only %d items available)", index, len(l.currentItems))
		}
		l.mu.RUnlock()
	}

	log.Printf("[LAUNCHER-KEY] Key press not handled: key=%d, state=%d", key, state)
	return false
}

func (l *Launcher) onTabPressed() bool {
	text, _ := l.searchEntry.GetText()
	log.Printf("[LAUNCHER-TAB] onTabPressed called with text: '%s'", text)

	log.Printf("[LAUNCHER-TAB] Creating hook context for tab hooks")
	hookCtx := l.createHookContext(nil)
	if hookCtx == nil {
		log.Printf("[LAUNCHER-TAB] ERROR: Failed to create hook context")
		return false
	}

	log.Printf("[LAUNCHER-TAB] Executing tab hooks")
	result := l.registry.GetHookRegistry().ExecuteTabHooks(l.ctx, hookCtx, text)
	log.Printf("[LAUNCHER-TAB] Tab hooks result: handled=%v, newText='%s'", result.Handled, result.NewText)

	if result.Handled {
		log.Printf("[LAUNCHER-TAB] Tab hooks handled, setting new text: '%s'", result.NewText)
		l.searchEntry.SetText(result.NewText)
		return true
	}

	log.Printf("[LAUNCHER-TAB] Tab hooks not handled, inserting first result into search box")
	l.mu.RLock()
	if len(l.currentItems) > 0 {
		firstItem := l.currentItems[0]
		l.mu.RUnlock()
		log.Printf("[LAUNCHER-TAB] Inserting first item title into search box: '%s'", firstItem.Title)
		l.searchEntry.SetText(firstItem.Title)
		l.searchEntry.SetPosition(-1)
		return true
	}
	l.mu.RUnlock()

	log.Printf("[LAUNCHER-TAB] No items available, allowing default behavior")
	return false
}

func (l *Launcher) shouldShowIcon(item *launcher.LauncherItem) bool {
	if !l.config.Launcher.Icons.EnableIcons {
		return false
	}

	allowedLaunchers := l.config.Launcher.Icons.IconsForLaunchers
	if len(allowedLaunchers) == 0 {
		return true
	}

	if item.Launcher == nil {
		return true
	}

	launcherName := item.Launcher.Name()
	for _, allowed := range allowedLaunchers {
		if allowed == launcherName {
			return true
		}
	}

	return false
}

func (l *Launcher) createHookContext(item *launcher.LauncherItem) *launcher.HookContext {
	if l == nil {
		log.Printf("[HOOK-CONTEXT] ERROR: Launcher is nil, cannot create hook context")
		return nil
	}

	launcherName := ""
	if item != nil && item.Launcher != nil {
		launcherName = item.Launcher.Name()
	}

	var query string
	if l != nil {
		query = l.currentInput
	}

	var config *config.Config
	if l != nil {
		config = l.config
	}

	var refreshUIChan chan<- launcher.RefreshUIRequest
	if l != nil {
		refreshUIChan = l.refreshUIChan
	}

	var statusChan chan<- launcher.StatusRequest
	if l != nil {
		statusChan = l.statusChan
	}

	var showLockScreen func() error
	if l.registry != nil {
		showLockScreen = l.registry.GetLockScreenCallback()
	}

	hookCtx := &launcher.HookContext{
		LauncherName:   launcherName,
		Query:          query,
		SelectedItem:   item,
		Config:         config,
		RefreshUI:      refreshUIChan,
		SendStatus:     statusChan,
		ShowLockScreen: showLockScreen,
	}

	log.Printf("[HOOK-CONTEXT] Created hook context: launcher='%s', query='%s', hasItem=%v, hasConfig=%v, hasCallbacks=%v",
		launcherName, query, item != nil, config != nil, refreshUIChan != nil && statusChan != nil && showLockScreen != nil)

	return hookCtx
}

func (l *Launcher) refreshResults() error {
	// Trigger a new search with the current input
	text, _ := l.searchEntry.GetText()
	l.onSearchChanged(text)
	return nil
}

func (l *Launcher) refreshResultsSync() error {
	return l.refreshResults()
}

func (l *Launcher) sendStatusMessageSync(msg string) error {
	return l.sendStatusMessage(msg)
}

func (l *Launcher) sendStatusMessage(msg string) error {
	// Send status message via IPC
	if l.app != nil && l.app.statusBar != nil {
		// TODO: Implement status message sending
		return nil
	}
	return nil
}

func (l *Launcher) handleRefreshUIRequests(ctx context.Context, ch <-chan launcher.RefreshUIRequest) {
	for {
		select {
		case req := <-ch:
			glib.IdleAdd(func() {
				err := l.refreshResults()
				select {
				case req.Response <- err:
				default:
				}
			})
		case <-ctx.Done():
			return
		}
	}
}

func (l *Launcher) handleStatusRequests(ctx context.Context, ch <-chan launcher.StatusRequest) {
	for {
		select {
		case req := <-ch:
			glib.IdleAdd(func() {
				err := l.sendStatusMessage(req.Message)
				select {
				case req.Response <- err:
				default:
				}
			})
		case <-ctx.Done():
			return
		}
	}
}

func (l *Launcher) navigateResult(direction int) {
	log.Printf("[LAUNCHER-NAV] navigateResult called with direction: %d", direction)
	if l == nil || l.resultList == nil {
		log.Printf("[LAUNCHER-NAV] ERROR: Launcher or result list is nil")
		return
	}

	selected := l.resultList.GetSelectedRow()
	var currentIndex int = -1
	if selected != nil {
		currentIndex = selected.GetIndex()
	}
	log.Printf("[LAUNCHER-NAV] Current selection index: %d", currentIndex)

	totalRows := int(l.resultList.GetChildren().Length())
	log.Printf("[LAUNCHER-NAV] Total rows available: %d", totalRows)

	var nextIndex int
	if currentIndex == -1 {
		if direction > 0 {
			nextIndex = 0
			log.Printf("[LAUNCHER-NAV] No selection, moving to first item (index 0)")
		} else {
			nextIndex = totalRows - 1
			log.Printf("[LAUNCHER-NAV] No selection, moving to last item (index %d)", nextIndex)
		}
	} else {
		nextIndex = currentIndex + direction
		log.Printf("[LAUNCHER-NAV] Calculating next index: %d + %d = %d", currentIndex, direction, nextIndex)

		if nextIndex < 0 {
			nextIndex = totalRows - 1
			log.Printf("[LAUNCHER-NAV] Wrapped to end: %d", nextIndex)
		} else if nextIndex >= totalRows {
			nextIndex = 0
			log.Printf("[LAUNCHER-NAV] Wrapped to beginning: %d", nextIndex)
		}
	}

	log.Printf("[LAUNCHER-NAV] Attempting to select row at index: %d", nextIndex)
	// Use GetRowAtIndex instead of NthData - this is the correct GTK API
	if row := l.resultList.GetRowAtIndex(nextIndex); row != nil {
		log.Printf("[LAUNCHER-NAV] Row found, selecting it")
		l.resultList.SelectRow(row)

		// Scroll the selected row into view
		if l.scrolledWindow != nil {
			vadj := l.scrolledWindow.GetVAdjustment()
			if vadj != nil {
				// Get row allocation to determine its position
				if widget := row.ToWidget(); widget != nil {
					alloc := widget.GetAllocation()
					rowY := alloc.GetY()
					rowHeight := alloc.GetHeight()

					// Get current scroll position and viewport size
					scrollY := vadj.GetValue()
					pageSize := vadj.GetPageSize()

					log.Printf("[LAUNCHER-NAV] Scroll check: rowY=%d, rowHeight=%d, scrollY=%.1f, pageSize=%.1f",
						rowY, rowHeight, scrollY, pageSize)

					// Check if row is visible
					rowTop := float64(rowY)
					rowBottom := float64(rowY + rowHeight)

					if rowTop < scrollY {
						// Row is above visible area, scroll up to show it
						log.Printf("[LAUNCHER-NAV] Scrolling up to show row")
						vadj.SetValue(rowTop)
					} else if rowBottom > scrollY+pageSize {
						// Row is below visible area, scroll down to show it
						log.Printf("[LAUNCHER-NAV] Scrolling down to show row")
						vadj.SetValue(rowBottom - pageSize)
					} else {
						log.Printf("[LAUNCHER-NAV] Row already visible, no scrolling needed")
					}
				} else {
					log.Printf("[LAUNCHER-NAV] WARNING: Could not get widget from row")
				}
			} else {
				log.Printf("[LAUNCHER-NAV] WARNING: Could not get vertical adjustment")
			}
		} else {
			log.Printf("[LAUNCHER-NAV] WARNING: Scrolled window is nil")
		}
		log.Printf("[LAUNCHER-NAV] Navigation completed successfully")
	} else {
		log.Printf("[LAUNCHER-NAV] ERROR: Could not get row at index %d", nextIndex)
	}
}

func (l *Launcher) Show() error {
	startTime := time.Now()
	defer func() {
		log.Printf("[LAUNCHER-SHOW] Show() completed in %v", time.Since(startTime))
	}()

	log.Printf("[LAUNCHER-SHOW] Show() called, checking if launcher is running")
	l.mu.Lock()
	if !l.running {
		log.Printf("[LAUNCHER-SHOW] Launcher not running, starting it")
		if err := l.Start(); err != nil {
			log.Printf("[LAUNCHER-SHOW] ERROR: Failed to start launcher: %v", err)
			l.mu.Unlock()
			return err
		}
		log.Printf("[LAUNCHER-SHOW] Launcher started successfully")
	} else {
		log.Printf("[LAUNCHER-SHOW] Launcher already running")
	}
	l.mu.Unlock()

	cfg := l.config.Launcher.Animation
	startY := -400
	targetY := cfg.TargetMargin
	distance := targetY - startY

	log.Printf("[LAUNCHER-SHOW] Animation config: enabled=%v, slideIn=%v, targetMargin=%d, duration=%dms",
		cfg.Enabled, cfg.EnableSlideIn, cfg.TargetMargin, cfg.SlideDuration)

	log.Printf("[LAUNCHER-SHOW] Setting initial margin to %d and showing window", startY)

	done := make(chan struct{})
	go func() {
		layer.SetMargin(unsafe.Pointer(l.window.Native()), layer.EdgeTop, startY)
		l.window.ShowAll()
		l.window.Present()
		close(done)
	}()

	select {
	case <-done:
		log.Printf("[LAUNCHER-SHOW] Window shown and presented")
	case <-time.After(5 * time.Second):
		log.Printf("[LAUNCHER-SHOW] WARNING: Window operations timed out after 5s")
	}

	l.searchEntry.SetText("")

	if cfg.Enabled && cfg.EnableSlideIn {
		log.Printf("[LAUNCHER-SHOW] Starting slide-in animation: distance=%d, duration=%dms", distance, cfg.SlideDuration)
		durationNs := int64(cfg.SlideDuration) * 1_000_000
		animStartTime := time.Now().UnixNano()

		animationTicks := 0
		l.window.AddTickCallback(func(w *gtk.Widget, frameClock *gdk.FrameClock) bool {
			animationTicks++

			tickStart := time.Now()
			elapsed := time.Now().UnixNano() - animStartTime

			if elapsed > durationNs*2 {
				log.Printf("[LAUNCHER-SHOW] WARNING: Animation timeout after %vms, forcing completion", elapsed/1_000_000)
				layer.SetMargin(unsafe.Pointer(w.Native()), layer.EdgeTop, targetY)
				l.searchEntry.GrabFocus()
				l.visible.Store(true)
				return false
			}

			progress := float64(elapsed) / float64(durationNs)

			if progress >= 1.0 {
				log.Printf("[LAUNCHER-SHOW] Animation completed after %d ticks, setting final margin to %d", animationTicks, targetY)
				layer.SetMargin(unsafe.Pointer(w.Native()), layer.EdgeTop, targetY)
				l.searchEntry.GrabFocus()
				l.visible.Store(true)
				log.Printf("[LAUNCHER-SHOW] Focus grabbed by search entry")
				tickDuration := time.Since(tickStart)
				if tickDuration > 50*time.Millisecond {
					log.Printf("[LAUNCHER-SHOW] WARNING: Final animation tick took %v", tickDuration)
				}
				return false
			}

			easedProgress := easeOutCubic(progress)
			currentY := startY + int(float64(distance)*easedProgress)
			layer.SetMargin(unsafe.Pointer(w.Native()), layer.EdgeTop, currentY)

			tickDuration := time.Since(tickStart)
			if tickDuration > 50*time.Millisecond {
				log.Printf("[LAUNCHER-SHOW] WARNING: Animation tick %d took %v (progress: %.2f)", animationTicks, tickDuration, progress)
			}
			return true
		})
	} else {
		log.Printf("[LAUNCHER-SHOW] Animation disabled, setting final margin to %d", targetY)
		layer.SetMargin(unsafe.Pointer(l.window.Native()), layer.EdgeTop, targetY)
		l.searchEntry.GrabFocus()
		log.Printf("[LAUNCHER-SHOW] Focus grabbed by search entry")
	}

	l.visible.Store(true)
	return nil
}

func (l *Launcher) Hide() {
	startTime := time.Now()
	defer func() {
		log.Printf("[LAUNCHER-HIDE] Hide() completed in %v", time.Since(startTime))
	}()

	log.Printf("[LAUNCHER-HIDE] Hide() called")
	l.mu.Lock()
	log.Printf("[LAUNCHER-HIDE] Stopping search timer and clearing items")
	l.stopAndDrainSearchTimer()
	l.currentItems = nil
	l.mu.Unlock()

	cfg := l.config.Launcher.Animation
	startY := cfg.TargetMargin
	targetY := -400
	distance := startY - targetY

	log.Printf("[LAUNCHER-HIDE] Animation config: enabled=%v, slideIn=%v, startY=%d, targetY=%d, distance=%d",
		cfg.Enabled, cfg.EnableSlideIn, startY, targetY, distance)

	if cfg.Enabled && cfg.EnableSlideIn {
		log.Printf("[LAUNCHER-HIDE] Starting slide-out animation: duration=%dms", cfg.SlideDuration)
		durationNs := int64(cfg.SlideDuration) * 1_000_000
		animStartTime := time.Now().UnixNano()

		animationTicks := 0
		l.window.AddTickCallback(func(w *gtk.Widget, frameClock *gdk.FrameClock) bool {
			animationTicks++

			tickStart := time.Now()
			elapsed := time.Now().UnixNano() - animStartTime

			if elapsed > durationNs*2 {
				log.Printf("[LAUNCHER-HIDE] WARNING: Animation timeout after %vms, forcing window hide", elapsed/1_000_000)
				l.window.Hide()
				l.searchEntry.SetText("")
				l.visible.Store(false)
				layer.SetMargin(unsafe.Pointer(l.window.Native()), layer.EdgeTop, cfg.TargetMargin)
				return false
			}

			progress := float64(elapsed) / float64(durationNs)

			if progress >= 1.0 {
				log.Printf("[LAUNCHER-HIDE] Animation completed after %d ticks, hiding window", animationTicks)
				l.window.Hide()
				l.searchEntry.SetText("")
				l.visible.Store(false)
				layer.SetMargin(unsafe.Pointer(l.window.Native()), layer.EdgeTop, cfg.TargetMargin)

				tickDuration := time.Since(tickStart)
				if tickDuration > 50*time.Millisecond {
					log.Printf("[LAUNCHER-HIDE] WARNING: Final hide animation tick took %v", tickDuration)
				}
				return false
			}

			easedProgress := easeOutCubic(progress)
			currentY := startY - int(float64(distance)*easedProgress)
			layer.SetMargin(unsafe.Pointer(w.Native()), layer.EdgeTop, currentY)

			tickDuration := time.Since(tickStart)
			if tickDuration > 50*time.Millisecond {
				log.Printf("[LAUNCHER-HIDE] WARNING: Hide animation tick %d took %v (progress: %.2f)", animationTicks, tickDuration, progress)
			}
			return true
		})
	} else {
		log.Printf("[LAUNCHER-HIDE] Animation disabled, hiding window immediately")
		l.window.Hide()
		l.searchEntry.SetText("")
		l.visible.Store(false)
		layer.SetMargin(unsafe.Pointer(l.window.Native()), layer.EdgeTop, cfg.TargetMargin)
		log.Printf("[LAUNCHER-HIDE] Window hidden and cleaned up")
	}
}

func (l *Launcher) stopAndDrainSearchTimer() {
	if l.searchTimer != nil {
		if !l.searchTimer.Stop() {
			// Timer already fired, drain the channel to prevent leaks
			// Check if channel is not nil before trying to drain
			if l.searchTimer.C != nil {
				select {
				case <-l.searchTimer.C:
				default:
				}
			}
		}
		l.searchTimer = nil
	}
}

func (l *Launcher) Toggle() error {
	startTime := time.Now()
	visible := l.visible.Load()

	if visible {
		// Launcher is already visible, do nothing (don't hide it)
		log.Printf("[LAUNCHER] Toggle() - launcher already visible, no action taken")
	} else {
		// Show the launcher
		err := l.Show()
		log.Printf("[LAUNCHER] Toggle() (show) completed in %v", time.Since(startTime))
		return err
	}

	return nil
}

func (l *Launcher) Start() error {
	log.Printf("Launcher.Start() - beginning")

	if l.running {
		log.Printf("Launcher already running")
		return ErrLauncherAlreadyRunning
	}

	log.Printf("Loading built-in launchers")
	if err := l.registry.LoadBuiltIn(); err != nil {
		log.Printf("Failed to load launchers: %v", err)
		return fmt.Errorf("failed to load launchers: %w", err)
	}

	// Set up lock screen callback
	if l.app != nil {
		l.registry.SetLockScreenCallback(l.app.ShowLockScreen)
	}

	// Get window dimensions for geometry hints
	width := l.config.Launcher.Window.Width
	height := l.config.Launcher.Window.Height
	if width <= 0 {
		width = 600
	}
	if height <= 0 {
		minHeightForResults := 5 * 44
		searchEntryHeight := 50
		extraPadding := 20
		height = minHeightForResults + searchEntryHeight + extraPadding
		if height < 500 {
			height = 500
		}
	}

	// Set geometry hints to enforce fixed window size
	geometry := gdk.Geometry{}
	geometry.SetMinWidth(width)
	geometry.SetMinHeight(height)
	geometry.SetMaxWidth(width)
	geometry.SetMaxHeight(height)
	geometry.SetBaseWidth(width)
	geometry.SetBaseHeight(height)

	// Use geometry hints with bitwise OR of hint flags
	var geometryMask gdk.WindowHints
	geometryMask |= gdk.WindowHints(1 << 1) // HINT_MIN_SIZE
	geometryMask |= gdk.WindowHints(1 << 2) // HINT_MAX_SIZE
	geometryMask |= gdk.WindowHints(1 << 3) // HINT_BASE_SIZE

	l.window.SetGeometryHints(l.window, geometry, geometryMask)

	// Set the actual window size
	l.window.SetDefaultSize(width, height)

	log.Printf("Initializing layer shell")
	layer.InitForWindow(unsafe.Pointer(l.window.Native()))
	layer.SetLayer(unsafe.Pointer(l.window.Native()), layer.LayerOverlay)
	layer.SetKeyboardMode(unsafe.Pointer(l.window.Native()), layer.KeyboardModeExclusive)
	// Explicitly set all anchors
	layer.SetAnchor(unsafe.Pointer(l.window.Native()), layer.EdgeTop, true)
	layer.SetAnchor(unsafe.Pointer(l.window.Native()), layer.EdgeBottom, false)
	layer.SetAnchor(unsafe.Pointer(l.window.Native()), layer.EdgeLeft, false)
	layer.SetAnchor(unsafe.Pointer(l.window.Native()), layer.EdgeRight, false)
	layer.SetMargin(unsafe.Pointer(l.window.Native()), layer.EdgeTop, 40)
	layer.SetExclusiveZone(unsafe.Pointer(l.window.Native()), 0)

	l.window.Connect("destroy", func() {
		l.Quit()
	})

	l.setupMonitorChangeHandler()

	l.running = true
	log.Printf("Launcher started successfully - window should be visible now")
	return nil
}

func (l *Launcher) Stop() error {
	l.mu.Lock()
	defer l.mu.Unlock()

	if !l.running {
		return nil
	}

	// Cancel context and close channels
	l.cancel()
	close(l.refreshUIChan)
	close(l.statusChan)

	if l.monitorDebounceSource != 0 {
		glib.SourceRemove(l.monitorDebounceSource)
		l.monitorDebounceSource = 0
	}

	if l.monitorHandler != 0 && l.display != nil {
		l.display.HandlerDisconnect(l.monitorHandler)
		l.monitorHandler = 0
	}

	l.registry.Cleanup()
	if l.iconCache != nil {
		l.iconCache.Clear()
	}
	l.window.Close()

	l.running = false
	return nil
}

func (l *Launcher) Quit() {
	if err := l.Stop(); err != nil {
		fmt.Printf("Error stopping launcher: %v\n", err)
	}
	l.app.Quit()
}

func (l *Launcher) setupMonitorChangeHandler() {
	if l.display == nil {
		log.Printf("[LAUNCHER] Display not available, skipping monitor change handler setup")
		return
	}

	l.display.Connect("monitor-added", func() {
		l.handleMonitorChange()
	})
	l.display.Connect("monitor-removed", func() {
		l.handleMonitorChange()
	})
}

func (l *Launcher) handleMonitorChange() {
	l.mu.Lock()

	if l.recreating {
		l.mu.Unlock()
		log.Printf("[LAUNCHER] Already recreating, skipping monitor change")
		return
	}

	wasVisible := l.visible.Load()
	if l.monitorDebounceSource != 0 {
		glib.SourceRemove(l.monitorDebounceSource)
		l.monitorDebounceSource = 0
	}
	l.mu.Unlock()

	log.Printf("[LAUNCHER] Monitor configuration changed, was visible=%v", wasVisible)

	l.mu.Lock()
	l.recreating = true
	l.monitorDebounceSource = glib.TimeoutAdd(500, func() bool {
		l.mu.Lock()
		l.monitorDebounceSource = 0
		if wasVisible {
			log.Printf("[LAUNCHER] Reconfiguring launcher for new monitor configuration")
			l.mu.Unlock()

			if l.visible.Load() {
				l.mu.Lock()
				l.Hide()
				l.mu.Unlock()

				glib.TimeoutAdd(100, func() bool {
					l.mu.Lock()
					err := l.Show()
					l.recreating = false
					l.mu.Unlock()

					if err != nil {
						log.Printf("[LAUNCHER] Failed to re-show launcher after monitor change: %v", err)
					}
					return false
				})
			} else {
				l.mu.Lock()
				l.recreating = false
				l.mu.Unlock()
			}
		} else {
			l.recreating = false
			l.mu.Unlock()
		}
		return false
	})
	l.mu.Unlock()
}

func (l *Launcher) IsRunning() bool {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.running
}

func (l *Launcher) updateFooter(input string) {
	// Update footer based on launcher context
	var footerText string

	if l.footerLabel == nil {
		return
	}

	// Check for launcher-specific input using registry
	_, launcher, _ := l.registry.FindLauncherForInput(input)

	if launcher != nil {
		// Launcher-specific mode
		footerText = launcher.Name()
		if footerText == "" {
			footerText = "Launcher"
		} else {
			// Capitalize first letter
			runes := []rune(footerText)
			if len(runes) > 0 {
				runes[0] = []rune(strings.ToUpper(string(runes[0])))[0]
				footerText = string(runes)
			}
		}
	} else if strings.HasPrefix(input, ">") {
		// Command mode
		command := strings.TrimSpace(input[1:])
		if command != "" {
			footerText = fmt.Sprintf("Command: %s", command)
		} else {
			footerText = "Commands"
		}
	} else {
		// Default app search
		footerText = "Applications"
	}

	// Update the footer label in the main thread
	glib.IdleAdd(func() bool {
		if l.footerLabel != nil {
			l.footerLabel.SetText(footerText)
		}
		return false
	})

	// Update color preview if this is a color launcher
	if launcher != nil && launcher.Name() == "color" {
		l.updateColorPreview(input)
	} else {
		// Hide color preview for non-color launchers
		glib.IdleAdd(func() bool {
			if l.colorPreviewBox != nil {
				l.colorPreviewBox.Hide()
			}
			return false
		})
	}
}

func (l *Launcher) updateColorPreview(input string) {
	glib.IdleAdd(func() bool {
		if l.colorPreviewBox == nil || l.colorPreviewWidget == nil {
			return false
		}

		color, ok := l.isValidColor(input)

		if ok {
			css := fmt.Sprintf(`
				#color-preview-widget {
					background-color: %s;
					border-radius: 4px;
					border: 1px solid rgba(255, 255, 255, 0.3);
				}
			`, color)

			styleProvider, err := gtk.CssProviderNew()
			if err == nil {
				if err := styleProvider.LoadFromData(css); err == nil {
					if styleCtx, err := l.colorPreviewWidget.GetStyleContext(); err == nil {
						styleCtx.AddProvider(styleProvider, gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
					}
				}
			}

			l.colorPreviewBox.ShowAll()
		} else {
			l.colorPreviewBox.Hide()
		}

		return false
	})
}

func (l *Launcher) isValidColor(input string) (string, bool) {
	input = strings.TrimSpace(input)
	if input == "" {
		return "", false
	}

	hexPattern := regexp.MustCompile(`^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$`)
	if hexPattern.MatchString(input) {
		normalized := input
		if len(input) > 0 && input[0] != '#' {
			normalized = "#" + normalized
		}
		if len(normalized) == 4 {
			normalized = "#" + string([]byte{normalized[1], normalized[1], normalized[2], normalized[2], normalized[3], normalized[3]})
		} else if len(normalized) == 5 {
			normalized = "#" + string([]byte{normalized[1], normalized[1], normalized[2], normalized[2], normalized[3], normalized[3], normalized[4], normalized[4]})
		}
		return normalized, true
	}

	namedColors := map[string]string{
		"red": "#ff0000", "green": "#00ff00", "blue": "#0000ff",
		"white": "#ffffff", "black": "#000000",
		"yellow": "#ffff00", "cyan": "#00ffff", "magenta": "#ff00ff",
		"gray": "#808080", "grey": "#808080",
		"orange": "#ffa500", "purple": "#800080", "pink": "#ffc0cb",
		"brown": "#a52a2a",
	}
	if hex, ok := namedColors[strings.ToLower(input)]; ok {
		return hex, true
	}

	return "", false
}

func (l *Launcher) IsVisible() bool {
	return l.visible.Load()
}

// parseHexColor parses a hex color string to RGBA uint32 for gdk.Pixbuf.Fill
func parseHexColor(hex string) (uint32, bool) {
	if len(hex) == 0 {
		return 0, false
	}

	if hex[0] == '#' {
		hex = hex[1:]
	}

	var r, g, b, a uint8

	switch len(hex) {
	case 3: // RGB shorthand
		r = parseHexByte(hex[0]) * 17
		g = parseHexByte(hex[1]) * 17
		b = parseHexByte(hex[2]) * 17
		a = 255
	case 4: // RGBA shorthand
		r = parseHexByte(hex[0]) * 17
		g = parseHexByte(hex[1]) * 17
		b = parseHexByte(hex[2]) * 17
		a = parseHexByte(hex[3]) * 17
	case 6: // RGB
		r = parseHexByte(hex[0])<<4 | parseHexByte(hex[1])
		g = parseHexByte(hex[2])<<4 | parseHexByte(hex[3])
		b = parseHexByte(hex[4])<<4 | parseHexByte(hex[5])
		a = 255
	case 8: // RGBA
		r = parseHexByte(hex[0])<<4 | parseHexByte(hex[1])
		g = parseHexByte(hex[2])<<4 | parseHexByte(hex[3])
		b = parseHexByte(hex[4])<<4 | parseHexByte(hex[5])
		a = parseHexByte(hex[6])<<4 | parseHexByte(hex[7])
	default:
		return 0, false
	}

	// RGBA format for gdk.Pixbuf.Fill is 0xAABBGGRR
	return uint32(a)<<24 | uint32(b)<<16 | uint32(g)<<8 | uint32(r), true
}

// parseHexByte parses a single hex character to its value
func parseHexByte(c byte) uint8 {
	switch {
	case c >= '0' && c <= '9':
		return c - '0'
	case c >= 'a' && c <= 'f':
		return c - 'a' + 10
	case c >= 'A' && c <= 'F':
		return c - 'A' + 10
	default:
		return 0
	}
}
