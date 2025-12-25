package core

import (
	"errors"
	"fmt"
	"log"
	"strings"
	"sync"
	"unsafe"

	"github.com/gotk3/gotk3/gdk"
	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/config"
	"github.com/sigma/locus-go/internal/launcher"
	"github.com/sigma/locus-go/internal/layer"
)

var (
	ErrLauncherAlreadyRunning = errors.New("launcher is already running")
)

type Launcher struct {
	app          *App
	config       *config.Config
	window       *gtk.Window
	searchEntry  *gtk.Entry
	resultList   *gtk.ListBox
	registry     *launcher.LauncherRegistry
	currentInput string
	currentItems []*launcher.LauncherItem
	running      bool
	visible      bool
	mu           sync.RWMutex
}

func NewLauncher(app *App, cfg *config.Config) (*Launcher, error) {
	window, err := gtk.WindowNew(gtk.WINDOW_TOPLEVEL)
	if err != nil {
		return nil, fmt.Errorf("failed to create window: %w", err)
	}

	window.SetDecorated(false)
	window.SetModal(true)
	window.SetSkipTaskbarHint(true)
	window.SetSkipPagerHint(true)
	window.SetTypeHint(gdk.WINDOW_TYPE_HINT_DIALOG)
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
	box.PackStart(searchEntry, false, false, 0)

	scrolledWindow, err := gtk.ScrolledWindowNew(nil, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create scrolled window: %w", err)
	}

	scrolledWindow.SetPolicy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
	box.PackStart(scrolledWindow, true, true, 0)

	resultList, err := gtk.ListBoxNew()
	if err != nil {
		return nil, fmt.Errorf("failed to create result list: %w", err)
	}

	resultList.SetName("result-list")
	scrolledWindow.Add(resultList)

	registry := launcher.NewLauncherRegistry(cfg)

	l := &Launcher{
		app:         app,
		config:      cfg,
		window:      window,
		searchEntry: searchEntry,
		resultList:  resultList,
		registry:    registry,
	}

	l.setupSignals()

	return l, nil
}

func (l *Launcher) setupSignals() {
	// Temporarily disable changed handler
	// l.searchEntry.Connect("changed", func() {
	// 	text, _ := l.searchEntry.GetText()
	// 	l.onSearchChanged(text)
	// })

	// Temporarily disable activate handler
	// l.searchEntry.Connect("activate", func() {
	// 	l.onActivate()
	// })

	// Temporarily disable key-press-event handler
	// l.searchEntry.Connect("key-press-event", func(event *gdk.Event) bool {
	// 	keyEvent := gdk.EventKeyNewFromEvent(event)
	// 	return l.onKeyPress(keyEvent)
	// })

	// Temporarily disable row-activated handler
	// l.resultList.Connect("row-activated", func(list *gtk.ListBox, row *gtk.ListBoxRow) {
	// 	l.onRowActivated(row)
	// })

	// Temporarily disable focus-out-event handler
	// l.window.Connect("focus-out-event", func(event *gdk.Event) bool {
	// 	l.Hide()
	// 	return false
	// })
}

func (l *Launcher) onSearchChanged(text string) {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.currentInput = text

	if strings.TrimSpace(text) == "" {
		return
	}

	items, err := l.registry.Search(text)
	if err != nil {
		fmt.Printf("Search error: %v\n", err)
		return
	}

	l.updateResults(items)
}

func (l *Launcher) updateResults(items []*launcher.LauncherItem) {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.currentItems = items

	l.resultList.GetChildren().Foreach(func(child interface{}) {
		if row, ok := child.(*gtk.ListBoxRow); ok {
			l.resultList.Remove(row)
		}
	})

	for _, item := range items {
		row, err := l.createResultRow(item)
		if err != nil {
			fmt.Printf("Failed to create row: %v\n", err)
			continue
		}
		l.resultList.Add(row)
		row.ShowAll()
	}

	if len(items) > 0 {
		children := l.resultList.GetChildren()
		if children.Length() > 0 {
			if row, ok := children.NthData(0).(*gtk.ListBoxRow); ok {
				l.resultList.SelectRow(row)
			}
		}
	}
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

	label.SetHAlign(gtk.ALIGN_START)
	box.PackStart(label, true, true, 0)

	if item.Subtitle != "" {
		subLabel, err := gtk.LabelNew(item.Subtitle)
		if err != nil {
			return nil, err
		}

		subLabel.SetHAlign(gtk.ALIGN_START)
		subLabel.SetMarginStart(16)
		box.PackStart(subLabel, true, true, 0)
	}

	row.Add(box)
	return row, nil
}

func (l *Launcher) onActivate() {
	selected := l.resultList.GetSelectedRow()

	if selected != nil {
		l.onRowActivated(selected)
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
	}

	return false
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
	l.mu.Lock()
	defer l.mu.Unlock()

	if !l.running {
		log.Printf("Launcher not running, starting...")
		if err := l.Start(); err != nil {
			log.Printf("Failed to start launcher: %v", err)
			return err
		}
		log.Printf("Launcher started successfully")
	}

	log.Printf("Calling window.ShowAll() and Present()")
	l.window.ShowAll()
	l.window.Present()
	l.searchEntry.SetText("")
	l.searchEntry.GrabFocus()
	l.visible = true
	log.Printf("Launcher should now be visible")

	return nil
}

func (l *Launcher) Hide() {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.window.Hide()
	l.searchEntry.SetText("")
	l.currentItems = nil
	l.visible = false
}

func (l *Launcher) Toggle() error {
	l.mu.RLock()
	visible := l.visible
	l.mu.RUnlock()

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
		height = 400
	}
	l.window.SetDefaultSize(width, height)

	log.Printf("Loading built-in launchers")
	if err := l.registry.LoadBuiltIn(); err != nil {
		log.Printf("Failed to load launchers: %v", err)
		return fmt.Errorf("failed to load launchers: %w", err)
	}

	log.Printf("Realizing window")
	// Realize the window before layer shell initialization
	l.window.Realize()

	log.Printf("Initializing layer shell")
	layer.InitForWindow(unsafe.Pointer(l.window.Native()))
	layer.SetLayer(unsafe.Pointer(l.window.Native()), layer.LayerOverlay)
	layer.SetKeyboardMode(unsafe.Pointer(l.window.Native()), layer.KeyboardModeExclusive)
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
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.visible
}
