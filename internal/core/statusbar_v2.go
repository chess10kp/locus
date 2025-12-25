package core

import (
	"errors"
	"fmt"
	"log"
	"sync"
	"unsafe"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/config"
	"github.com/sigma/locus-go/internal/layer"
	"github.com/sigma/locus-go/internal/statusbar"
	statusbarModules "github.com/sigma/locus-go/internal/statusbar/modules"
)

var (
	ErrStatusBarAlreadyRunning = errors.New("status bar is already running")
)

type StatusBar struct {
	app        *App
	config     *config.Config
	window     *gtk.Window
	container  *gtk.Box
	registry   *statusbar.ModuleRegistry
	scheduler  *statusbar.UpdateScheduler
	widgets    map[string]gtk.IWidget
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

	registry := statusbar.DefaultRegistry()
	scheduler := statusbar.NewUpdateScheduler(registry)

	return &StatusBar{
		app:       app,
		config:    cfg,
		window:    window,
		container: container,
		registry:  registry,
		scheduler: scheduler,
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

	if err := sb.loadModules(); err != nil {
		return fmt.Errorf("failed to load modules: %w", err)
	}

	if err := sb.createWidgets(); err != nil {
		return fmt.Errorf("failed to create widgets: %w", err)
	}

	if err := sb.setupLayerShell(); err != nil {
		return fmt.Errorf("failed to setup layer shell: %w", err)
	}

	if err := sb.scheduler.Start(); err != nil {
		return fmt.Errorf("failed to start scheduler: %w", err)
	}

	sb.window.Connect("destroy", func() {
		close(sb.stopUpdate)
		sb.Quit()
	})

	sb.window.ShowAll()

	sb.running = true
	sb.stopUpdate = make(chan struct{})

	log.Printf("Status bar started successfully")

	return nil
}

func (sb *StatusBar) Stop() error {
	sb.mu.Lock()
	defer sb.mu.Unlock()

	if !sb.running {
		return nil
	}

	sb.scheduler.Stop()
	sb.registry.CleanupAll()
	sb.window.Close()

	sb.running = false

	log.Printf("Status bar stopped")

	return nil
}

func (sb *StatusBar) Cleanup() {
	sb.Stop()
}

func (sb *StatusBar) Quit() {
	if err := sb.Stop(); err != nil {
		log.Printf("Error stopping status bar: %v", err)
	}
	sb.app.Quit()
}

func (sb *StatusBar) Update() error {
	sb.scheduler.UpdateAll()
	return nil
}

func (sb *StatusBar) HandleIPC(msg string) error {
	sb.scheduler.HandleIPCMessage(msg)
	return nil
}

func (sb *StatusBar) loadModules() error {
	modulesConfig := sb.config.StatusBar.Modules

	for _, moduleName := range modulesConfig {
		moduleConfig := sb.config.StatusBar.ModuleConfigs[moduleName]

		var module statusbar.Module
		var err error

		if moduleName == "launcher" {
			launcherFactory := statusbarModules.NewLauncherModuleFactory(sb.app)
			module, err = launcherFactory.CreateModule(moduleConfig.ToMap())
			if err == nil {
				sb.registry.RegisterModule(module)
			}
		} else {
			module, err = sb.registry.CreateModule(moduleName, moduleConfig.ToMap())
			if err != nil {
				log.Printf("Failed to create module '%s': %v", moduleName, err)
				continue
			}

			if err := sb.registry.RegisterModule(module); err != nil {
				log.Printf("Failed to register module '%s': %v", moduleName, err)
				continue
			}
		}

		log.Printf("Loaded module: %s", moduleName)
	}

	return nil
}

func (sb *StatusBar) createWidgets() error {
	sb.widgets = make(map[string]gtk.IWidget)
	modules := sb.registry.ListModules()

	for _, moduleName := range modules {
		widget, err := sb.registry.CreateWidgetForModule(moduleName)
		if err != nil {
			log.Printf("Failed to create widget for module '%s': %v", moduleName, err)
			continue
		}

		if err := sb.scheduler.ScheduleModule(moduleName, widget); err != nil {
			log.Printf("Failed to schedule module '%s': %v", moduleName, err)
		}

		sb.widgets[moduleName] = widget
		sb.container.PackStart(widget, false, false, 0)

		log.Printf("Created widget for module: %s", moduleName)
	}

	return nil
}

func (sb *StatusBar) setupLayerShell() error {
	nativePtr := unsafe.Pointer(sb.window.Native())
	layer.InitForWindow(nativePtr)
	layer.SetLayer(nativePtr, layer.LayerTop)
	layer.SetAnchor(nativePtr, layer.EdgeLeft, true)
	layer.SetAnchor(nativePtr, layer.EdgeRight, true)
	layer.SetAnchor(nativePtr, layer.EdgeTop, true)
	layer.AutoExclusiveZoneEnable(nativePtr)
	layer.SetKeyboardMode(nativePtr, layer.KeyboardModeNone)

	fmt.Printf("Statusbar: enabled auto-exclusive zone\n")

	return nil
}

func (sb *StatusBar) UpdateModule(name string) error {
	return sb.scheduler.UpdateModule(name)
}

func (sb *StatusBar) TriggerManualUpdate(name string) error {
	return sb.scheduler.TriggerManualUpdate(name)
}

func (sb *StatusBar) GetModuleWidget(name string) (gtk.IWidget, bool) {
	return sb.scheduler.GetModuleWidget(name)
}

func (sb *StatusBar) IsRunning() bool {
	sb.mu.RLock()
	defer sb.mu.RUnlock()
	return sb.running
}
