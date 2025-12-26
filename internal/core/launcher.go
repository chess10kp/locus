package core

import (
	"context"
	"errors"
	"fmt"
	"log"
	"sync"
	"sync/atomic"
	"time"
	"unsafe"

	"github.com/gotk3/gotk3/gdk"
	"github.com/gotk3/gotk3/glib"
	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/config"
	"github.com/sigma/locus-go/internal/launcher"
	"github.com/sigma/locus-go/internal/layer"
)

var debugLogger = log.New(log.Writer(), "[LAUNCHER-DEBUG] ", log.LstdFlags|log.Lmicroseconds)

var (
	ErrLauncherAlreadyRunning = errors.New("launcher is already running")
)

type Launcher struct {
	app            *App
	config         *config.Config
	window         *gtk.Window
	searchEntry    *gtk.Entry
	resultList     *gtk.ListBox
	hideButton     *gtk.Button
	registry       *launcher.LauncherRegistry
	currentInput   string
	currentItems   []*launcher.LauncherItem
	scrolledWindow *gtk.ScrolledWindow
	running        bool
	visible        atomic.Bool
	searchTimer    *time.Timer
	searchVersion  int64 // Track search version to prevent race conditions
	mu             sync.RWMutex
	refreshUIChan  chan launcher.RefreshUIRequest
	statusChan     chan launcher.StatusRequest
	ctx            context.Context
	cancel         context.CancelFunc
}

func NewLauncher(app *App, cfg *config.Config) (*Launcher, error) {
	window, err := gtk.WindowNew(gtk.WINDOW_TOPLEVEL)
	if err != nil {
		return nil, fmt.Errorf("failed to create window: %w", err)
	}

	window.SetDecorated(false)
	window.SetSkipTaskbarHint(true)
	window.SetSkipPagerHint(true)
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

	// Create hide button
	hideButton, err := gtk.ButtonNewWithLabel("Hide")
	if err != nil {
		return nil, fmt.Errorf("failed to create hide button: %w", err)
	}
	hideButton.SetName("hide-button")
	hbox.PackStart(hideButton, false, false, 0)

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

	registry := launcher.NewLauncherRegistry(cfg)

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
		hideButton:     hideButton,
		scrolledWindow: scrolledWindow,
		registry:       registry,
		refreshUIChan:  refreshUIChan,
		statusChan:     statusChan,
		ctx:            ctx,
		cancel:         cancel,
	}

	// Start goroutines to handle channel requests
	go l.handleRefreshUIRequests(ctx, refreshUIChan)
	go l.handleStatusRequests(ctx, statusChan)

	l.setupSignals()

	// Connect hide button
	hideButton.Connect("clicked", func() {
		l.Hide()
	})

	return l, nil
}

func (l *Launcher) setupSignals() {
	l.searchEntry.Connect("changed", func() {
		text, _ := l.searchEntry.GetText()
		l.onSearchChanged(text)
	})

	l.searchEntry.Connect("activate", func() {
		l.onActivate()
	})

	l.searchEntry.Connect("key-press-event", func(entry *gtk.Entry, event *gdk.Event) bool {
		keyEvent := gdk.EventKeyNewFromEvent(event)
		return l.onKeyPress(keyEvent)
	})

	l.resultList.Connect("row-activated", func(list *gtk.ListBox, row *gtk.ListBoxRow) {
		l.onRowActivated(row)
	})

	l.window.Connect("focus-out-event", func(window *gtk.Window, event *gdk.Event) bool {
		l.Hide()
		return false
	})
}

func (l *Launcher) onSearchChanged(text string) {
	searchStart := time.Now()
	debugLogger.Printf("SEARCH_CHANGED: text='%s' len=%d", text, len(text))
	fmt.Printf("[SEARCH] Input changed to: '%s' (len=%d)\n", text, len(text))

	l.mu.Lock()
	defer l.mu.Unlock()

	l.currentInput = text

	// Increment search version for this request
	version := atomic.AddInt64(&l.searchVersion, 1)
	searchVersion := version // Copy for closure
	debugLogger.Printf("SEARCH_CHANGED: version=%d, scheduled search in %dms", version, l.config.Launcher.Search.DebounceDelay)

	// Cancel previous timer if exists
	if l.searchTimer != nil {
		l.stopAndDrainSearchTimer()
		debugLogger.Printf("SEARCH_CHANGED: cancelled previous timer")
	}

	// Start new timer with configured debounce delay
	debounceMs := l.config.Launcher.Search.DebounceDelay
	l.searchTimer = time.AfterFunc(time.Duration(debounceMs)*time.Millisecond, func() {
		timerFireTime := time.Now()
		debugLogger.Printf("SEARCH_TIMER: fired for version=%d, query='%s', delay was %v", version, text, timerFireTime.Sub(searchStart))

		// Run search in a goroutine to avoid blocking UI
		go func(query string, version int64) {
			searchGoroutineStart := time.Now()
			debugLogger.Printf("SEARCH_GOROUTINE: started for version=%d, query='%s'", version, query)

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
				debugLogger.Printf("UI_IDLE: callback started for version=%d", version)

				l.mu.RLock()
				currentVersion := l.searchVersion
				l.mu.RUnlock()

				// Skip stale results from older searches
				if version != currentVersion {
					debugLogger.Printf("UI_IDLE: skipping stale results for version=%d (current=%d)", version, currentVersion)
					return false // Don't repeat
				}

				l.updateResults(items, version)

				debugLogger.Printf("UI_IDLE: completed for version=%d in %v, total search time %v",
					version, time.Since(idleCallbackStart), time.Since(searchStart))
				return false // Don't repeat
			})
		}(text, searchVersion)
	})
}

func (l *Launcher) updateResults(items []*launcher.LauncherItem, version int64) {
	l.mu.Lock()
	success := l.updateResultsUnsafe(items, version)
	l.mu.Unlock()

	if success {
		l.resultList.ShowAll()
		l.resultList.QueueDraw()
		l.scrolledWindow.QueueDraw()
	}
}

func (l *Launcher) updateResultsUnsafe(items []*launcher.LauncherItem, version int64) bool {
	updateStart := time.Now()
	debugLogger.Printf("UPDATE_RESULTS: started for version=%d, %d items", version, len(items))

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
	childCount := children.Length()
	children.Foreach(func(child interface{}) {
		if row, ok := child.(*gtk.ListBoxRow); ok {
			l.resultList.Remove(row)
		}
	})
	debugLogger.Printf("UPDATE_RESULTS: cleared %d existing children in %v", childCount, time.Since(clearStart))

	// Create new result rows
	renderStart := time.Now()
	for i, item := range items {
		row, err := l.createResultRow(item)
		if err != nil {
			debugLogger.Printf("UPDATE_RESULTS: failed to create row %d: %v", i, err)
			fmt.Printf("Failed to create row: %v\n", err)
			continue
		}
		l.resultList.Add(row)
	}
	debugLogger.Printf("UPDATE_RESULTS: rendered %d new rows in %v", len(items), time.Since(renderStart))

	// Select first row if any
	if len(items) > 0 {
		children := l.resultList.GetChildren()
		if children.Length() > 0 {
			if row, ok := children.NthData(0).(*gtk.ListBoxRow); ok {
				l.resultList.SelectRow(row)
			}
		}
	}

	debugLogger.Printf("UPDATE_RESULTS: completed for version=%d in %v", version, time.Since(updateStart))
	return true
}

func (l *Launcher) createResultRow(item *launcher.LauncherItem) (*gtk.ListBoxRow, error) {
	row, err := gtk.ListBoxRowNew()
	if err != nil {
		return nil, err
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

		icon.SetFromIconName(item.Icon, gtk.ICON_SIZE_LARGE_TOOLBAR)
		box.PackStart(icon, false, false, 0)
	}

	label, err := gtk.LabelNew(item.Title)
	if err != nil {
		return nil, err
	}

	if label != nil {
		label.SetHAlign(gtk.ALIGN_START)
	}
	box.PackStart(label, true, true, 0)

	if item.Subtitle != "" {
		subLabel, err := gtk.LabelNew(item.Subtitle)
		if err != nil {
			return nil, err
		}

		if subLabel != nil {
			subLabel.SetHAlign(gtk.ALIGN_START)
			subLabel.SetMarginStart(16)
		}
		box.PackStart(subLabel, true, true, 0)
	}

	row.Add(box)
	row.Show()
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
	l.mu.RLock()
	index := row.GetIndex()
	if index < 0 || index >= len(l.currentItems) {
		l.mu.RUnlock()
		return
	}
	item := l.currentItems[index]
	l.mu.RUnlock()

	// Execute hooks first
	hookCtx := l.createHookContext(item)
	result := l.registry.GetHookRegistry().ExecuteSelectHooks(l.ctx, hookCtx, item.ActionData)

	if result.Handled {
		l.Hide()
		return
	}

	// Fall back to default execution
	if err := l.registry.Execute(item); err != nil {
		fmt.Printf("Failed to execute item: %v\n", err)
	}

	l.Hide()
}

func (l *Launcher) onKeyPress(event *gdk.EventKey) bool {
	key := event.KeyVal()

	switch key {
	case gdk.KEY_Escape:
		l.Hide()
		return true
	case gdk.KEY_Down, gdk.KEY_j:
		l.navigateResult(1)
		return true
	case gdk.KEY_Up, gdk.KEY_k:
		l.navigateResult(-1)
		return true
	case gdk.KEY_Tab:
		return l.onTabPressed()
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
	launcherName := ""
	if item != nil && item.Launcher != nil {
		launcherName = item.Launcher.Name()
	}

	return &launcher.HookContext{
		LauncherName: launcherName,
		Query:        l.currentInput,
		SelectedItem: item,
		Config:       l.config,
		RefreshUI:    l.refreshUIChan,
		SendStatus:   l.statusChan,
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
	selected := l.resultList.GetSelectedRow()
	children := l.resultList.GetChildren()

	if children.Length() == 0 {
		return
	}

	var currentIndex int = -1
	if selected != nil {
		currentIndex = selected.GetIndex()
	}

	var nextIndex int
	if currentIndex == -1 {
		if direction > 0 {
			nextIndex = 0
		} else {
			nextIndex = int(children.Length()) - 1
		}
	} else {
		nextIndex = currentIndex + direction
		if nextIndex < 0 {
			nextIndex = int(children.Length()) - 1
		} else if nextIndex >= int(children.Length()) {
			nextIndex = 0
		}
	}

	if row, ok := children.NthData(uint(nextIndex)).(*gtk.ListBoxRow); ok {
		l.resultList.SelectRow(row)
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
	log.Printf("Calling window.ShowAll() and Present()")
	l.window.ShowAll()
	l.window.Present()
	l.searchEntry.SetText("")
	l.searchEntry.GrabFocus()

	// Update visibility flag atomically
	l.visible.Store(true)

	log.Printf("Launcher should now be visible")
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
			select {
			case <-l.searchTimer.C:
			default:
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

	log.Printf("Loading built-in launchers")
	if err := l.registry.LoadBuiltIn(); err != nil {
		log.Printf("Failed to load launchers: %v", err)
		return fmt.Errorf("failed to load launchers: %w", err)
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

func (l *Launcher) IsVisible() bool {
	return l.visible.Load()
}
