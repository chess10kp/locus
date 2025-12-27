package core

import (
	"context"
	"errors"
	"fmt"
	"log"
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
)

var debugLogger = log.New(log.Writer(), "[LAUNCHER-DEBUG] ", log.LstdFlags|log.Lmicroseconds)

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
	app            *App
	config         *config.Config
	window         *gtk.Window
	searchEntry    *gtk.Entry
	resultList     *gtk.ListBox
	registry       *launcher.LauncherRegistry
	iconCache      *launcher.IconCache
	currentInput   string
	currentItems   []*launcher.LauncherItem
	scrolledWindow *gtk.ScrolledWindow
	badgesBox      *gtk.Box
	footerBox      *gtk.Box
	footerLabel    *gtk.Label
	running        bool
	visible        atomic.Bool
	searchTimer    *time.Timer
	searchVersion  int64 // Track search version to prevent race conditions

	mu            sync.RWMutex
	refreshUIChan chan launcher.RefreshUIRequest
	statusChan    chan launcher.StatusRequest
	ctx           context.Context
	cancel        context.CancelFunc
}

func NewLauncher(app *App, cfg *config.Config) (*Launcher, error) {
	window, err := gtk.WindowNew(gtk.WINDOW_TOPLEVEL)
	if err != nil {
		return nil, fmt.Errorf("failed to create window: %w", err)
	}

	window.SetDecorated(false)
	window.SetSkipTaskbarHint(true)
	window.SetSkipPagerHint(true)
	window.SetResizable(false)
	window.SetName("launcher-window")

	box, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to create box: %w", err)
	}

	window.Add(box)

	searchEntry, err := gtk.EntryNew()
	if err != nil {
		return nil, fmt.Errorf("failed to create search entry: %w", err)
	}

	searchEntry.SetPlaceholderText("Search or type a command...")
	searchEntry.SetName("launcher-entry")

	// Create horizontal box for search entry and buttons
	hbox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 5)
	if err != nil {
		return nil, fmt.Errorf("failed to create hbox: %w", err)
	}
	hbox.PackStart(searchEntry, true, true, 0)

	box.PackStart(hbox, false, false, 0)

	scrolledWindow, err := gtk.ScrolledWindowNew(nil, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create scrolled window: %w", err)
	}

	scrolledWindow.SetPolicy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
	scrolledWindow.SetVExpand(true)
	scrolledWindow.SetMinContentHeight(5 * 44) // Minimum height for 5 results
	box.PackStart(scrolledWindow, true, true, 0)

	resultList, err := gtk.ListBoxNew()
	if err != nil {
		return nil, fmt.Errorf("failed to create result list: %w", err)
	}

	resultList.SetName("result-list")
	resultList.SetVExpand(true)
	scrolledWindow.Add(resultList)
	scrolledWindow.ShowAll()

	// Create badges box for keyboard shortcuts
	badgesBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 8)
	if err != nil {
		return nil, fmt.Errorf("failed to create badges box: %w", err)
	}
	badgesBox.SetName("badges-box")
	badgesBox.SetHAlign(gtk.ALIGN_FILL)

	// Add keyboard shortcut hints
	shortcuts := []string{"Select: Return", "↓: Ctrl+J", "↑: Ctrl+K"}
	for _, shortcut := range shortcuts {
		label, err := gtk.LabelNew(shortcut)
		if err != nil {
			continue
		}
		label.SetName("badge-label")
		badgesBox.PackStart(label, false, false, 0)
	}
	box.PackStart(badgesBox, false, false, 4)

	// Create footer box for context information
	footerBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to create footer box: %w", err)
	}
	footerBox.SetName("footer-box")
	footerBox.SetHAlign(gtk.ALIGN_FILL)

	footerLabel, err := gtk.LabelNew("Applications")
	if err != nil {
		return nil, fmt.Errorf("failed to create footer label: %w", err)
	}
	footerLabel.SetName("footer-label")
	footerLabel.SetHAlign(gtk.ALIGN_START)
	footerLabel.SetHExpand(true)
	footerBox.PackStart(footerLabel, true, true, 0)

	box.PackStart(footerBox, false, false, 4)

	registry := launcher.NewLauncherRegistry(cfg)

	// Create icon cache
	iconCache, err := launcher.NewIconCache(cfg)
	if err != nil {
		log.Printf("Failed to create icon cache: %v", err)
		// Continue without cache - icons will use default GTK sizes
		iconCache = nil
	}

	// Create channels for hook context
	refreshUIChan := make(chan launcher.RefreshUIRequest, 1)
	statusChan := make(chan launcher.StatusRequest, 10) // Buffer for multiple status messages
	ctx, cancel := context.WithCancel(context.Background())

	l := &Launcher{
		app:            app,
		config:         cfg,
		window:         window,
		searchEntry:    searchEntry,
		resultList:     resultList,
		scrolledWindow: scrolledWindow,
		badgesBox:      badgesBox,
		footerBox:      footerBox,
		footerLabel:    footerLabel,
		registry:       registry,
		iconCache:      iconCache,
		refreshUIChan:  refreshUIChan,
		statusChan:     statusChan,
		ctx:            ctx,
		cancel:         cancel,
	}

	// Start goroutines to handle channel requests
	go l.handleRefreshUIRequests(ctx, refreshUIChan)
	go l.handleStatusRequests(ctx, statusChan)

	// Setup launcher-specific styles
	SetupLauncherStyles(l.config)

	l.setupSignals()

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

	l.window.Connect("focus-out-event", func(window *gtk.Window, event *gdk.Event) bool {
		defer func() {
			if r := recover(); r != nil {
				log.Printf("[LAUNCHER] Panic recovered in focus out: %v", r)
			}
		}()
		if l == nil {
			return false
		}
		l.Hide()
		return false
	})
}

func (l *Launcher) onSearchChanged(text string) {
	searchStart := time.Now()
	visible := l.visible.Load()
	debugLogger.Printf("SEARCH_CHANGED: text='%s' len=%d visible=%v", text, len(text), visible)
	fmt.Printf("[SEARCH] Input changed to: '%s' (len=%d)\n", text, len(text))

	// Add debug info about current state
	currentItems := 0
	if l.currentItems != nil {
		currentItems = len(l.currentItems)
	}
	children := l.resultList.GetChildren()
	childCount := 0
	if children != nil {
		childCount = int(children.Length())
	}
	debugLogger.Printf("SEARCH_CHANGED: current state - currentItems=%d, children=%d", currentItems, childCount)

	l.mu.Lock()
	defer l.mu.Unlock()

	l.currentInput = text

	// Update footer based on launcher context
	l.updateFooter(text)

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

	debugLogger.Printf("SEARCH_CHANGED: version=%d, len=%d, scheduled search in %dms (adaptive)", version, len(text), debounceMs)

	// Cancel previous timer if exists
	if l.searchTimer != nil {
		l.stopAndDrainSearchTimer()
		debugLogger.Printf("SEARCH_CHANGED: cancelled previous timer")
	}

	// Start new timer with adaptive debounce delay
	l.searchTimer = time.AfterFunc(time.Duration(debounceMs)*time.Millisecond, func() {
		timerFireTime := time.Now()
		debugLogger.Printf("SEARCH_TIMER: fired for version=%d, query='%s', delay was %v", version, text, timerFireTime.Sub(searchStart))

		// Check if this timer callback is still valid before proceeding
		currentVersion := atomic.LoadInt64(&l.searchVersion)
		if version != currentVersion {
			debugLogger.Printf("SEARCH_TIMER: abandoning timer for version=%d, current=%d", version, currentVersion)
			return
		}

		// Run search in a goroutine to avoid blocking UI
		go func(query string, version int64, startTime time.Time) {
			defer func() {
				if r := recover(); r != nil {
					log.Printf("[SEARCH-PANIC] Recovered from panic: %v", r)
					debugLogger.Printf("SEARCH_PANIC: Recovered from panic in search goroutine: %v", r)
				}
			}()

			searchGoroutineStart := time.Now()
			debugLogger.Printf("SEARCH_GOROUTINE: started for version=%d, query='%s'", version, query)

			// Double-check version before expensive search operation
			currentVersion = atomic.LoadInt64(&l.searchVersion)
			if version != currentVersion {
				debugLogger.Printf("SEARCH_GOROUTINE: abandoning search for version=%d, current=%d", version, currentVersion)
				return
			}

			items, err := l.registry.Search(query)
			if err != nil {
				debugLogger.Printf("SEARCH_GOROUTINE: error for version=%d: %v", version, err)
				fmt.Printf("Search error: %v\n", err)
				return
			}

			searchCompleted := time.Now()
			debugLogger.Printf("SEARCH_GOROUTINE: completed for version=%d, found %d items in %v", version, len(items), searchCompleted.Sub(searchGoroutineStart))

			// Update UI in main thread using IdleAdd
			glib.IdleAdd(func() bool {
				idleCallbackStart := time.Now()
				debugLogger.Printf("UI_IDLE: callback started for version=%d with %d items", version, len(items))

				// Get current version atomically to avoid race conditions
				currentVersion := atomic.LoadInt64(&l.searchVersion)

				// Skip stale results from older searches
				if version != currentVersion {
					debugLogger.Printf("UI_IDLE: skipping stale results for version=%d (current=%d)", version, currentVersion)
					return false // Don't repeat
				}

				debugLogger.Printf("UI_IDLE: calling updateResults for version=%d", version)
				l.updateResults(items, version)

				debugLogger.Printf("UI_IDLE: completed for version=%d in %v, total search time %v",
					version, time.Since(idleCallbackStart), time.Since(searchStart))
				return false // Don't repeat
			})
		}(text, searchVersion, searchStart)
	})

	// For zero delay (empty string), also trigger immediate update
	if debounceMs == 0 {
		debugLogger.Printf("SEARCH_CHANGED: immediate search requested for empty string")
	}
}

func (l *Launcher) updateResults(items []*launcher.LauncherItem, version int64) {
	// Check if widgets are still valid
	if l.resultList == nil || l.window == nil {
		debugLogger.Printf("UPDATE_RESULTS: widgets are nil, skipping update")
		return
	}

	l.mu.Lock()
	defer l.mu.Unlock()
	l.updateResultsUnsafe(items, version)
}

func (l *Launcher) updateResultsUnsafe(items []*launcher.LauncherItem, version int64) bool {
	updateStart := time.Now()
	debugLogger.Printf("UPDATE_RESULTS: started for version=%d, %d items", version, len(items))

	// Check if resultList is still valid
	if l.resultList == nil {
		debugLogger.Printf("UPDATE_RESULTS: resultList is nil, returning false")
		return false
	}

	// Double-check version is still current
	currentVersion := atomic.LoadInt64(&l.searchVersion)
	if version != currentVersion {
		debugLogger.Printf("UPDATE_RESULTS: skipping stale update for version=%d (current=%d)", version, currentVersion)
		return false // Skip stale update
	}

	l.currentItems = items

	// Clear existing results
	clearStart := time.Now()

	children := l.resultList.GetChildren()
	var childCount int
	if children != nil {
		childCount = int(children.Length())
	}
	debugLogger.Printf("UPDATE_RESULTS: before clear: %d children", childCount)

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

	debugLogger.Printf("UPDATE_RESULTS: removed %d rows in %v", removedCount, time.Since(clearStart))

	// Verify clear
	childrenAfterClear := l.resultList.GetChildren()
	afterCount := 0
	if childrenAfterClear != nil {
		afterCount = int(childrenAfterClear.Length())
	}
	debugLogger.Printf("UPDATE_RESULTS: after clear: %d children remaining", afterCount)

	// Create new result rows
	renderStart := time.Now()
	successCount := 0
	if len(items) > 0 {
		debugLogger.Printf("UPDATE_RESULTS: first item title: '%s'", items[0].Title)
	}
	for i, item := range items {
		row, err := l.createResultRow(item, i)
		if err != nil {
			debugLogger.Printf("UPDATE_RESULTS: failed to create row %d for item '%s': %v", i, item.Title, err)
			fmt.Printf("Failed to create row: %v\n", err)
			continue
		}
		l.resultList.Add(row)
		successCount++
		debugLogger.Printf("UPDATE_RESULTS: added row %d: '%s'", i, item.Title)
	}

	childrenAfterAdd := l.resultList.GetChildren()
	addChildCount := 0
	if childrenAfterAdd != nil {
		addChildCount = int(childrenAfterAdd.Length())
	}
	debugLogger.Printf("UPDATE_RESULTS: after add: %d children (rendered %d/%d rows in %v)", addChildCount, successCount, len(items), time.Since(renderStart))

	// Make sure the scrolled window is visible
	if l.scrolledWindow != nil {
		l.scrolledWindow.ShowAll()
	}

	// Show all widgets in the list
	l.resultList.ShowAll()

	// Force the listbox to redraw
	l.resultList.QueueDraw()
	if l.scrolledWindow != nil {
		l.scrolledWindow.QueueDraw()
	}

	debugLogger.Printf("UPDATE_RESULTS: ShowAll and QueueDraw completed")

	// Select first row if any
	if len(items) > 0 {
		children := l.resultList.GetChildren()
		if children != nil && children.Length() > 0 {
			if child := children.NthData(0); child != nil {
				if row, ok := child.(*gtk.ListBoxRow); ok {
					l.resultList.SelectRow(row)
				}
			}
		}
	}

	debugLogger.Printf("UPDATE_RESULTS: completed for version=%d in %v", version, time.Since(updateStart))
	return true
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

	box, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 8)
	if err != nil {
		return nil, err
	}

	box.SetMarginStart(8)
	box.SetMarginEnd(8)
	box.SetMarginTop(8)
	box.SetMarginBottom(8)

	if item.Icon != "" {
		icon, err := gtk.ImageNew()
		if err != nil {
			return nil, err
		}

		// Always use consistent icon size
		iconSize := l.config.Launcher.Icons.IconSize
		if iconSize <= 0 {
			iconSize = 32 // Default consistent size
		}

		var pixbuf *gdk.Pixbuf
		var loadErr error

		if l.iconCache != nil {
			// Use cache if available (includes fallback handling)
			pixbuf, loadErr = l.iconCache.GetIcon(item.Icon, iconSize)
		} else {
			// Load directly from theme at custom size with fallback
			theme, themeErr := gtk.IconThemeGetDefault()
			if themeErr == nil {
				// Try the requested icon first
				pixbuf, loadErr = theme.LoadIcon(item.Icon, iconSize, gtk.ICON_LOOKUP_USE_BUILTIN)
				if loadErr != nil || pixbuf == nil {
					// Try fallback icon
					fallback := l.config.Launcher.Icons.FallbackIcon
					if fallback == "" {
						fallback = "image-missing"
					}
					if item.Icon != fallback {
						pixbuf, loadErr = theme.LoadIcon(fallback, iconSize, gtk.ICON_LOOKUP_USE_BUILTIN)
					}
				}
			}
		}

		if loadErr == nil && pixbuf != nil {
			// Ensure pixbuf is exactly the right size
			if pixbuf.GetWidth() != iconSize || pixbuf.GetHeight() != iconSize {
				// Scale to exact size if needed
				scaled, scaleErr := pixbuf.ScaleSimple(iconSize, iconSize, gdk.INTERP_BILINEAR)
				if scaleErr == nil && scaled != nil {
					pixbuf = scaled
				}
			}
			icon.SetFromPixbuf(pixbuf)
		} else {
			// Create a blank icon at the custom size to ensure consistency
			// This ensures all icons have the same dimensions even when loading fails
			pixbuf, loadErr = gdk.PixbufNew(gdk.COLORSPACE_RGB, true, 8, iconSize, iconSize)
			if loadErr == nil && pixbuf != nil {
				// Fill with transparent background
				pixbuf.Fill(0x00000000) // RGBA: transparent
				icon.SetFromPixbuf(pixbuf)
			} else {
				// Ultimate fallback
				icon.SetFromIconName(item.Icon, gtk.ICON_SIZE_LARGE_TOOLBAR)
			}
		}

		box.PackStart(icon, false, false, 0)
		icon.Show()
	}

	// Create a vertical box for title and subtitle
	textBox, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 2)
	if err != nil {
		return nil, err
	}
	textBox.SetHAlign(gtk.ALIGN_START)
	box.PackStart(textBox, true, true, 0)

	label, err := gtk.LabelNew(item.Title)
	if err != nil {
		return nil, err
	}

	label.SetHAlign(gtk.ALIGN_START)
	textBox.PackStart(label, false, false, 0)
	label.Show()

	if item.Subtitle != "" {
		subLabel, err := gtk.LabelNew(item.Subtitle)
		if err != nil {
			return nil, err
		}

		subLabel.SetHAlign(gtk.ALIGN_START)
		textBox.PackStart(subLabel, false, false, 0)
		subLabel.Show()
	}
	textBox.Show()

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

func (l *Launcher) onActivate() {
	text, _ := l.searchEntry.GetText()

	// Execute enter hooks first
	hookCtx := l.createHookContext(nil)
	result := l.registry.GetHookRegistry().ExecuteEnterHooks(l.ctx, hookCtx, text)

	if result.Handled {
		l.Hide()
		return
	}

	// Fall back to executing selected item, or first item if none selected
	selected := l.resultList.GetSelectedRow()
	if selected != nil {
		l.onRowActivated(selected)
	} else if len(l.currentItems) > 0 {
		item := l.currentItems[0]
		hookCtx := l.createHookContext(item)
		result := l.registry.GetHookRegistry().ExecuteSelectHooks(l.ctx, hookCtx, item.ActionData)
		if result.Handled {
			l.Hide()
		}
	}
}

func (l *Launcher) onRowActivated(row *gtk.ListBoxRow) {
	if l == nil || row == nil {
		return
	}
	l.mu.RLock()
	index := row.GetIndex()
	if index < 0 || index >= len(l.currentItems) {
		l.mu.RUnlock()
		return
	}
	item := l.currentItems[index]
	l.mu.RUnlock()

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

func (l *Launcher) onKeyPress(event *gdk.EventKey) bool {
	if event == nil {
		return false
	}
	key := event.KeyVal()
	state := event.State()

	if l.resultList == nil {
		return false
	}

	switch key {
	case gdk.KEY_Escape:
		l.Hide()
		return true
	case gdk.KEY_Down:
		l.navigateResult(1)
		return true
	case gdk.KEY_Up:
		l.navigateResult(-1)
		return true
	case gdk.KEY_Tab:
		return l.onTabPressed()
	case gdk.KEY_n, gdk.KEY_j:
		if state&uint(gdk.CONTROL_MASK) != 0 {
			l.navigateResult(1)
			return true
		}
		return false
	case gdk.KEY_p, gdk.KEY_k: // TODO: add to config file;
		if state&uint(gdk.CONTROL_MASK) != 0 {
			l.navigateResult(-1)
			return true
		}
		return false
	}

	// Check for Alt+number (1-9) to directly activate corresponding entry
	if state&uint(gdk.MOD1_MASK) != 0 {
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
			return false
		}

		l.mu.RLock()
		if index < len(l.currentItems) {
			row := l.resultList.GetRowAtIndex(index)
			if row != nil {
				l.mu.RUnlock()
				l.onRowActivated(row)
				return true
			}
		}
		l.mu.RUnlock()
	}

	// Check for Ctrl+number (1-9) to execute launcher-specific action on corresponding entry
	if state&uint(gdk.CONTROL_MASK) != 0 {
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
			return false
		}

		l.mu.RLock()
		index := number - 1
		if index < len(l.currentItems) {
			item := l.currentItems[index]
			if item.Launcher != nil {
				action, exists := item.Launcher.GetCtrlNumberAction(number)
				if exists && action != nil {
					l.mu.RUnlock()
					if err := action(item); err != nil {
						fmt.Printf("Ctrl+%d action failed: %v\n", number, err)
					} else {
						l.Hide()
					}
					return true
				}
			}
		}
		l.mu.RUnlock()
	}

	return false
}

func (l *Launcher) onTabPressed() bool {
	text, _ := l.searchEntry.GetText()
	hookCtx := l.createHookContext(nil)
	result := l.registry.GetHookRegistry().ExecuteTabHooks(l.ctx, hookCtx, text)

	if result.Handled {
		l.searchEntry.SetText(result.NewText)
		return true
	}

	return false
}

func (l *Launcher) createHookContext(item *launcher.LauncherItem) *launcher.HookContext {
	if l == nil {
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

	return &launcher.HookContext{
		LauncherName:   launcherName,
		Query:          query,
		SelectedItem:   item,
		Config:         config,
		RefreshUI:      refreshUIChan,
		SendStatus:     statusChan,
		ShowLockScreen: showLockScreen,
	}
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
	if l == nil || l.resultList == nil {
		return
	}
	selected := l.resultList.GetSelectedRow()

	var currentIndex int = -1
	if selected != nil {
		currentIndex = selected.GetIndex()
	}

	var nextIndex int
	if currentIndex == -1 {
		if direction > 0 {
			nextIndex = 0
		} else {
			nextIndex = int(l.resultList.GetChildren().Length()) - 1
		}
	} else {
		nextIndex = currentIndex + direction
		totalRows := int(l.resultList.GetChildren().Length())
		if nextIndex < 0 {
			nextIndex = totalRows - 1
		} else if nextIndex >= totalRows {
			nextIndex = 0
		}
	}

	// Use GetRowAtIndex instead of NthData - this is the correct GTK API
	if row := l.resultList.GetRowAtIndex(nextIndex); row != nil {
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

					// Check if row is visible
					rowTop := float64(rowY)
					rowBottom := float64(rowY + rowHeight)

					if rowTop < scrollY {
						// Row is above visible area, scroll up to show it
						vadj.SetValue(rowTop)
					} else if rowBottom > scrollY+pageSize {
						// Row is below visible area, scroll down to show it
						vadj.SetValue(rowBottom - pageSize)
					}
				}
			}
		}
	}
}

func (l *Launcher) Show() error {
	log.Printf("Launcher.Show() called, running=%v", l.running)

	// Acquire lock only for internal state changes
	l.mu.Lock()
	if !l.running {
		log.Printf("Launcher not running, starting...")
		if err := l.Start(); err != nil {
			l.mu.Unlock()
			log.Printf("Failed to start launcher: %v", err)
			return err
		}
		log.Printf("Launcher started successfully")
	}
	l.mu.Unlock()

	// GTK calls happen without holding lock
	debugLogger.Printf("SHOW: calling window.ShowAll()")
	l.window.ShowAll()
	debugLogger.Printf("SHOW: calling window.Present()")
	l.window.Present()
	debugLogger.Printf("SHOW: setting search entry text to empty")
	l.searchEntry.SetText("")
	debugLogger.Printf("SHOW: grabbing focus")
	l.searchEntry.GrabFocus()

	// Update visibility flag atomically
	debugLogger.Printf("SHOW: setting visible flag to true")
	l.visible.Store(true)
	debugLogger.Printf("SHOW: Show() complete")

	return nil
}

func (l *Launcher) Hide() {
	// Acquire lock only for internal state changes
	l.mu.Lock()
	l.stopAndDrainSearchTimer()
	l.currentItems = nil
	l.mu.Unlock()

	// GTK calls happen without holding lock
	l.window.Hide()
	l.searchEntry.SetText("")

	// Update visibility flag atomically
	l.visible.Store(false)
}

func (l *Launcher) stopAndDrainSearchTimer() {
	if l.searchTimer != nil {
		if !l.searchTimer.Stop() {
			// Timer already fired, drain the channel to prevent leaks
			// Check if channel is not nil before trying to drain
			if l.searchTimer.C != nil {
				select {
				case <-l.searchTimer.C:
					debugLogger.Printf("TIMER_DRAIN: successfully drained timer channel")
				default:
					debugLogger.Printf("TIMER_DRAIN: timer channel was empty")
				}
			}
		}
		l.searchTimer = nil
	}
}

func (l *Launcher) Toggle() error {
	visible := l.visible.Load()

	if visible {
		l.Hide()
	} else {
		return l.Show()
	}

	return nil
}

func (l *Launcher) Start() error {
	log.Printf("Launcher.Start() - beginning")

	if l.running {
		log.Printf("Launcher already running")
		return ErrLauncherAlreadyRunning
	}

	log.Printf("Setting window size")
	width := l.config.Launcher.Window.Width
	height := l.config.Launcher.Window.Height
	if width <= 0 {
		width = 600
	}
	if height <= 0 {
		// Calculate minimum height to show at least 5 results
		// Each result row is approximately: 8px (margin top) + 16px (font) + 8px (margin bottom) + 12px (padding) = 44px
		// Plus search entry height (~50px) and some padding
		minHeightForResults := 5 * 44                                   // 5 rows × ~44px each
		searchEntryHeight := 50                                         // Approximate search entry height
		extraPadding := 20                                              // Extra padding
		height = minHeightForResults + searchEntryHeight + extraPadding // ~290px minimum
		if height < 500 {
			height = 500 // Default to 500px if calculated height is smaller
		}
	}
	l.window.SetDefaultSize(width, height)
	l.window.SetResizable(false)

	log.Printf("Loading built-in launchers")
	if err := l.registry.LoadBuiltIn(); err != nil {
		log.Printf("Failed to load launchers: %v", err)
		return fmt.Errorf("failed to load launchers: %w", err)
	}

	// Set up lock screen callback
	if l.app != nil {
		l.registry.SetLockScreenCallback(l.app.ShowLockScreen)
	}

	log.Printf("Initializing layer shell")
	layer.InitForWindow(unsafe.Pointer(l.window.Native()))
	layer.SetLayer(unsafe.Pointer(l.window.Native()), layer.LayerOverlay)
	layer.SetKeyboardMode(unsafe.Pointer(l.window.Native()), layer.KeyboardModeExclusive)
	layer.SetAnchor(unsafe.Pointer(l.window.Native()), layer.EdgeTop, true)
	layer.SetMargin(unsafe.Pointer(l.window.Native()), layer.EdgeTop, 40)
	layer.SetExclusiveZone(unsafe.Pointer(l.window.Native()), 0)

	l.window.Connect("destroy", func() {
		l.Quit()
	})

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
}

func (l *Launcher) IsVisible() bool {
	return l.visible.Load()
}
