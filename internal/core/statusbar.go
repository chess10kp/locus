package core

import (
	"errors"
	"fmt"
	"sync"
	"time"
	"unsafe"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/config"
	"github.com/sigma/locus-go/internal/layer"
	"github.com/sigma/locus-go/internal/statusbar"
)

var (
	ErrStatusBarAlreadyRunning = errors.New("status bar is already running")
)

type StatusBar struct {
	app        *App
	config     *config.Config
	window     *gtk.Window
	container  *gtk.Box
	manager    *statusbar.ModuleManager
	widgets    map[string]*gtk.Label
	running    bool
	stopUpdate chan struct{}
	mu         sync.RWMutex
}

func NewStatusBar(app *App, cfg *config.Config) (*StatusBar, error) {
	window, err := gtk.WindowNew(gtk.WINDOW_TOPLEVEL)
	if err != nil {
		return nil, fmt.Errorf("failed to create window: %w", err)
	}

	container, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to create container: %w", err)
	}

	window.Add(container)

	manager := statusbar.NewModuleManager(app, cfg)

	return &StatusBar{
		app:       app,
		config:    cfg,
		window:    window,
		container: container,
		manager:   manager,
	}, nil
}

func (sb *StatusBar) Start() error {
	sb.mu.Lock()
	defer sb.mu.Unlock()

	if sb.running {
		return ErrStatusBarAlreadyRunning
	}

	sb.window.SetTitle(sb.config.AppName)
	sb.window.SetDecorated(false)
	sb.window.SetResizable(false)
	sb.window.SetName("statusbar")

	height := sb.config.StatusBar.Height
	if height > 0 {
		sb.window.SetDefaultSize(-1, height)
	}

	if err := sb.manager.LoadModules(sb.config.StatusBar.Modules); err != nil {
		return fmt.Errorf("failed to load modules: %w", err)
	}

	sb.widgets = make(map[string]*gtk.Label)
	modules := sb.manager.GetModules()

	for _, module := range modules {
		widget := module.CreateWidget()

		if widget.Type == statusbar.WidgetTypeButton {
			if launcherModule, ok := module.(*statusbar.LauncherModule); ok {
				button, err := gtk.ButtonNewWithLabel(widget.Value)
				if err == nil {
					button.SetRelief(gtk.RELIEF_NONE)
					button.SetName("launcher-button")
					sb.container.PackStart(button, false, false, 0)
					launcherModule.SetButton(button)

					button.Connect("clicked", func() {
						module.HandleClick(widget)
					})
				}
			}
		} else {
			label, _ := gtk.LabelNew(widget.Value)
			sb.widgets[module.Name()] = label
			label.SetName("module-" + module.Name())
			sb.container.PackStart(label, false, false, 0)
		}
	}

	layer.InitForWindow(unsafe.Pointer(sb.window.Native()))
	layer.SetLayer(unsafe.Pointer(sb.window.Native()), layer.LayerTop)
	layer.SetAnchor(unsafe.Pointer(sb.window.Native()), layer.EdgeLeft, true)
	layer.SetAnchor(unsafe.Pointer(sb.window.Native()), layer.EdgeRight, true)
	layer.SetAnchor(unsafe.Pointer(sb.window.Native()), layer.EdgeTop, true)
	layer.SetExclusiveZone(unsafe.Pointer(sb.window.Native()), height)
	layer.SetKeyboardMode(unsafe.Pointer(sb.window.Native()), layer.KeyboardModeNone)

	sb.window.Connect("destroy", func() {
		close(sb.stopUpdate)
		sb.Quit()
	})

	sb.window.ShowAll()

	sb.running = true
	sb.stopUpdate = make(chan struct{})
	go sb.updatePeriodicModules()

	return nil
}

func (sb *StatusBar) Stop() error {
	sb.mu.Lock()
	defer sb.mu.Unlock()

	if !sb.running {
		return nil
	}

	sb.manager.Cleanup()
	sb.window.Close()

	sb.running = false
	return nil
}

func (sb *StatusBar) Cleanup() {
	sb.Stop()
}

func (sb *StatusBar) Quit() {
	if err := sb.Stop(); err != nil {
		fmt.Printf("Error stopping status bar: %v\n", err)
	}
	sb.app.Quit()
}

func (sb *StatusBar) Update() error {
	sb.updatePeriodicModules()
	return nil
}

func (sb *StatusBar) HandleIPC(msg string) error {
	sb.manager.HandleIPCMessage(msg)
	return nil
}

func (sb *StatusBar) updatePeriodicModules() {
	modules := sb.manager.GetModules()
	for _, module := range modules {
		if module.UpdateMode() == statusbar.UpdateModePeriodic {
			widget := module.CreateWidget()
			label, ok := sb.widgets[module.Name()]
			if ok && widget.Value != "" {
				label.SetText(widget.Value)
			}
		}
	}
}

func (sb *StatusBar) updateLoop() {
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			sb.updatePeriodicModules()
		case <-sb.stopUpdate:
			return
		}
	}
}

func (sb *StatusBar) IsRunning() bool {
	sb.mu.RLock()
	defer sb.mu.RUnlock()
	return sb.running
}
