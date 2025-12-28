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
	"github.com/gotk3/gotk3/pango"
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
	gridFlowBox    *gtk.FlowBox
	registry       *launcher.LauncherRegistry
	iconCache      *launcher.IconCache
	thumbnailCache *launcher.ThumbnailCache
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
	gridMode       bool

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

	box.SetVExpand(true)
	box.SetHExpand(false)
	// Let the window expand as needed for content
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
	hbox.SetHExpand(true)
	hbox.PackStart(searchEntry, true, true, 0)

	box.PackStart(hbox, false, false, 0)

	scrolledWindow, err := gtk.ScrolledWindowNew(nil, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create scrolled window: %w", err)
	}

	scrolledWindow.SetPolicy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
	scrolledWindow.SetVExpand(true)
	scrolledWindow.SetHExpand(false)
	scrolledWindow.SetMinContentHeight(5 * 44) // Minimum height for 5 results
	scrolledWindow.SetSizeRequest(cfg.Launcher.Window.Width, -1)

	resultList, err := gtk.ListBoxNew()
	if err != nil {
		return nil, fmt.Errorf("failed to create result list: %w", err)
	}

	resultList.SetName("result-list")
	resultList.SetVExpand(true)
	resultList.SetHExpand(true) // Allow horizontal expansion for scrolling
	scrolledWindow.Add(resultList)
	scrolledWindow.ShowAll()

	// Add scrolled window to the main box
	box.PackStart(scrolledWindow, true, true, 0)

	// Create grid flow box for grid mode
	gridFlowBox, err := gtk.FlowBoxNew()
	if err != nil {
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

	// Create badges box for keyboard shortcuts
	badgesBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 8)
	if err != nil {
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
	footerBox.SetHAlign(gtk.ALIGN_START)
	footerBox.SetHExpand(false)
	footerBox.SetSizeRequest(cfg.Launcher.Window.Width, -1)
	footerBox.SetMarginBottom(12)

	footerLabel, err := gtk.LabelNew("Applications")
	if err != nil {
		return nil, fmt.Errorf("failed to create footer label: %w", err)
	}
	footerLabel.SetName("footer-label")
	footerLabel.SetHAlign(gtk.ALIGN_START)
	footerLabel.SetHExpand(false)
	footerBox.PackStart(footerLabel, true, false, 0)

	box.PackStart(footerBox, false, false, 4)

	registry := launcher.NewLauncherRegistry(cfg)

	// Create icon cache
	iconCache, err := launcher.NewIconCache(cfg)
	if err != nil {
		log.Printf("Failed to create icon cache: %v", err)
		// Continue without cache - icons will use default GTK sizes
		iconCache = nil
	}

	// Create thumbnail cache for grid items - DISABLED to prevent image corruption
	// thumbnailCache, err := launcher.NewThumbnailCache(100, 100)
	// if err != nil {
	// 	log.Printf("Failed to create thumbnail cache: %v", err)
	// 	// Continue without cache
	// 	thumbnailCache = nil
	// }
	var thumbnailCache *launcher.ThumbnailCache = nil

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
		gridFlowBox:    gridFlowBox,
		scrolledWindow: scrolledWindow,
		badgesBox:      badgesBox,
		footerBox:      footerBox,
		footerLabel:    footerLabel,
		registry:       registry,
		iconCache:      iconCache,
		thumbnailCache: thumbnailCache,
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

	// Cancel previous timer if exists
	if l.searchTimer != nil {
		l.stopAndDrainSearchTimer()
	}

	// Start new timer with adaptive debounce delay
	l.searchTimer = time.AfterFunc(time.Duration(debounceMs)*time.Millisecond, func() {
		// Check if this timer callback is still valid before proceeding
		currentVersion := atomic.LoadInt64(&l.searchVersion)
		if version != currentVersion {
			return
		}

		// Run search in a goroutine to avoid blocking UI
		go func(query string, version int64, startTime time.Time) {
			defer func() {
				if r := recover(); r != nil {
					log.Printf("[SEARCH-PANIC] Recovered from panic: %v", r)
				}
			}()

			// Double-check version before expensive search operation
			currentVersion = atomic.LoadInt64(&l.searchVersion)
			if version != currentVersion {
				return
			}

			items, err := l.registry.Search(query)
			if err != nil {
				fmt.Printf("Search error: %v\n", err)
				return
			}

			// Update UI in main thread using IdleAdd
			glib.IdleAdd(func() bool {
				// Get current version atomically to avoid race conditions
				currentVersion := atomic.LoadInt64(&l.searchVersion)

				// Skip stale results from older searches
				if version != currentVersion {
					return false // Don't repeat
				}

				l.updateResults(items, version)

				return false // Don't repeat
			})
		}(text, searchVersion, searchStart)
	})

	// For zero delay (empty string), also trigger immediate update
	if debounceMs == 0 {
	}
}

func (l *Launcher) updateResults(items []*launcher.LauncherItem, version int64) {
	// Check if widgets are still valid
	if l.resultList == nil || l.window == nil {
		return
	}

	l.mu.Lock()
	defer l.mu.Unlock()
	l.updateResultsUnsafe(items, version)
}

func (l *Launcher) updateResultsUnsafe(items []*launcher.LauncherItem, version int64) bool {
	// Check if resultList is still valid
	if l.resultList == nil {
		return false
	}

	// Double-check version is still current
	currentVersion := atomic.LoadInt64(&l.searchVersion)
	if version != currentVersion {
		return false // Skip stale update
	}

	l.currentItems = items

	// Check if we should use grid mode
	shouldUseGridMode := false
	var gridConfig *launcher.GridConfig

	// Determine if any launcher requests grid mode
	for _, item := range items {
		if item.Launcher != nil && item.Launcher.GetSizeMode() == launcher.LauncherSizeModeGrid {
			shouldUseGridMode = true
			gridConfig = item.Launcher.GetGridConfig()
			break
		}
	}

	// Explicitly disable grid mode for HelpLauncher items
	// HelpLauncher creates items that reference other launchers, which can incorrectly trigger grid mode
	if len(items) > 0 && items[0].Launcher != nil && items[0].Launcher.Name() == "help" {
		shouldUseGridMode = false
		gridConfig = nil
	}

	// Switch between list and grid mode
	if shouldUseGridMode != l.gridMode {
		l.switchViewMode(shouldUseGridMode, gridConfig)
	}

	if l.gridMode {
		l.updateGridResults(items)
	} else {
		l.updateListResults(items)
	}

	return true
}

func (l *Launcher) updateListResults(items []*launcher.LauncherItem) {
	// Remove all rows by repeatedly removing the first row
	for {
		row := l.resultList.GetRowAtIndex(0)
		if row == nil {
			break
		}
		l.resultList.Remove(row)
	}

	// Create new result rows
	for i, item := range items {
		row, err := l.createResultRow(item, i)
		if err != nil {
			fmt.Printf("Failed to create row: %v\n", err)
			continue
		}
		l.resultList.Add(row)
	}

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
}

func (l *Launcher) updateGridResults(items []*launcher.LauncherItem) {
	// Remove all children from flow box
	children := l.gridFlowBox.GetChildren()
	for i := uint(0); i < children.Length(); i++ {
		if child := children.NthData(i); child != nil {
			l.gridFlowBox.Remove(child.(gtk.IWidget))
		}
	}

	// Create new grid items
	for i, item := range items {
		gridItem, err := l.createGridItem(item, i)
		if err != nil {
			fmt.Printf("Failed to create grid item: %v\n", err)
			continue
		}
		l.gridFlowBox.Add(gridItem)
	}

	// Show all widgets in the grid
	l.gridFlowBox.ShowAll()

	// Force the grid to redraw
	l.gridFlowBox.QueueDraw()
	if l.scrolledWindow != nil {
		l.scrolledWindow.QueueDraw()
	}

	// Select first item if any
	if len(items) > 0 {
		children := l.gridFlowBox.GetChildren()
		if children != nil && children.Length() > 0 {
			if child := children.NthData(0); child != nil {
				if flowBoxChild, ok := child.(*gtk.FlowBoxChild); ok {
					l.gridFlowBox.SelectChild(flowBoxChild)
				}
			}
		}
	}
}

func (l *Launcher) switchViewMode(toGrid bool, gridConfig *launcher.GridConfig) {
	l.gridMode = toGrid

	if toGrid {
		// Switch to grid mode
		l.resultList.Hide()
		l.scrolledWindow.Remove(l.resultList)
		l.scrolledWindow.Add(l.gridFlowBox)
		l.gridFlowBox.ShowAll()

		// Apply grid configuration if available
		if gridConfig != nil {
			l.gridFlowBox.SetMaxChildrenPerLine(uint(gridConfig.Columns))
			l.gridFlowBox.SetColumnSpacing(uint(gridConfig.Spacing))
			l.gridFlowBox.SetRowSpacing(uint(gridConfig.Spacing))

			// Window size stays at configured default - no auto-resizing
		}
	} else {
		// Switch to list mode
		l.gridFlowBox.Hide()
		l.scrolledWindow.Remove(l.gridFlowBox)
		l.scrolledWindow.Add(l.resultList)
		l.resultList.ShowAll()

		// Window size stays at configured default - no auto-resizing
	}

	// Queue redraw
	l.window.QueueDraw()
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

	if item.Icon != "" && l.shouldShowIcon(item) {
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

		iconTextBox.PackStart(icon, false, false, 0)
		icon.SetVAlign(gtk.ALIGN_START)
		icon.Show()
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

	// Create container for grid item
	container, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 0)
	if err != nil {
		return nil, err
	}
	container.SetName("grid-item-container")

	// Load image if path is provided
	if item.ImagePath != "" {
		image, err := gtk.ImageNew()
		if err != nil {
			return nil, err
		}

		// Check cache first
		cacheKey := fmt.Sprintf("%s_%dx%d", item.ImagePath, gridConfig.ItemWidth)
		var pixbuf *gdk.Pixbuf

		if l.thumbnailCache != nil {
			// Try memory cache
			if cachedData, found := l.thumbnailCache.Get(cacheKey); found {
				pixbuf, err = gdk.PixbufNewFromData(cachedData, gdk.COLORSPACE_RGB, true, 8, gridConfig.ItemWidth, gridConfig.ItemHeight, gridConfig.ItemWidth*4)
				if err != nil {
					log.Printf("[GRID] Failed to load pixbuf from cache: %v", err)
				}
			}
		}

		// Load from file if not in cache
		if pixbuf == nil {
			pixbuf, err = gdk.PixbufNewFromFileAtScale(item.ImagePath, gridConfig.ItemWidth, gridConfig.ItemHeight, false)
			if err != nil {
				log.Printf("[GRID] Failed to load image %s: %v", item.ImagePath, err)
				// Create a placeholder
				pixbuf, err = gdk.PixbufNew(gdk.COLORSPACE_RGB, true, 8, gridConfig.ItemWidth, gridConfig.ItemHeight)
				if err == nil {
					pixbuf.Fill(0x22222222) // Dark gray placeholder
				}
			} else {
				// Cache the loaded pixbuf
				if l.thumbnailCache != nil {
					pixels := pixbuf.GetPixels()
					if len(pixels) > 0 {
						data := make([]byte, len(pixels))
						copy(data, pixels)
						l.thumbnailCache.Put(cacheKey, data)
					}
				}
			}
		}

		if pixbuf != nil {
			image.SetFromPixbuf(pixbuf)
		}
		container.PackStart(image, true, true, 0)
		image.Show()
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

		// Execute hooks first
		hookCtx := l.createHookContext(item)
		result := l.registry.GetHookRegistry().ExecuteSelectHooks(l.ctx, hookCtx, item.ActionData)
		if result.Handled {
			l.Hide()
			return
		}

		// Fall back to default execution
		if l.registry != nil {
			if err := l.registry.Execute(item); err != nil {
				log.Printf("[LAUNCHER] Failed to execute item: %v\n", err)
			}
		}

		l.Hide()
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
	l.mu.RLock()
	var title string
	if len(l.currentItems) > 0 {
		title = l.currentItems[0].Title
	}
	l.mu.RUnlock()

	if title != "" {
		l.searchEntry.SetText(title)
		l.searchEntry.SetPosition(-1)
		return true
	}

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

	// GTK calls happen without holding lock cause its ont eh same thread
	l.window.ShowAll()
	l.window.Present()

	// Apply slide-in animation with a small delay to ensure window is rendered
	glib.TimeoutAdd(10, func() bool {
		if styleCtx, err := l.window.GetStyleContext(); err == nil {
			styleCtx.AddClass("slide-in")
		}
		l.searchEntry.SetText("")
		l.searchEntry.GrabFocus()

		// Remove animation class after it completes
		glib.TimeoutAdd(uint(300), func() bool {
			if ctx, ctxErr := l.window.GetStyleContext(); ctxErr == nil {
				ctx.RemoveClass("slide-in")
			}
			return false
		})
		return false
	})

	// Update visibility flag atomically
	l.visible.Store(true)

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
				default:
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
