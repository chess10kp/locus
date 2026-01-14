package core

import (
	"errors"
	"fmt"
	"log"
	"net"
	"os"
	"strings"
	"sync"
	"unsafe"

	"github.com/chess10kp/locus/internal/config"
	"github.com/chess10kp/locus/internal/layer"
	"github.com/chess10kp/locus/internal/statusbar"
	statusbarModules "github.com/chess10kp/locus/internal/statusbar/modules"
	"github.com/gotk3/gotk3/gdk"
	"github.com/gotk3/gotk3/glib"
	"github.com/gotk3/gotk3/gtk"
)

var (
	ErrStatusBarAlreadyRunning = errors.New("status bar is already running")
)

type StatusBar struct {
	app                *App
	config             *config.Config
	windows            map[int]*gtk.Window
	containers         map[int]*gtk.Box
	screen             *gdk.Screen
	display            *gdk.Display
	registry           *statusbar.ModuleRegistry
	scheduler          *statusbar.UpdateScheduler
	widgets            map[string]gtk.IWidget
	running            bool
	stopUpdate         chan struct{}
	ipcRunning         bool
	ipcListener        net.Listener
	ipcSocket          string
	mu                       sync.RWMutex
	monitorDebounceSource    glib.SourceHandle
	monitorChangeTimerSource glib.SourceHandle
	recreating               bool
}

func NewStatusBar(app *App, cfg *config.Config) (*StatusBar, error) {
	// Get default screen for monitor tracking (legacy)
	screen, err := gdk.ScreenGetDefault()
	if err != nil {
		return nil, fmt.Errorf("failed to get default screen: %w", err)
	}

	// Get default display for monitor tracking
	display, err := gdk.DisplayGetDefault()
	if err != nil {
		return nil, fmt.Errorf("failed to get default display: %w", err)
	}

	registry := statusbar.DefaultRegistry()
	scheduler := statusbar.NewUpdateScheduler(registry)

	return &StatusBar{
		app:        app,
		config:     cfg,
		windows:    make(map[int]*gtk.Window),
		containers: make(map[int]*gtk.Box),
		screen:     screen,
		display:    display,
		registry:   registry,
		scheduler:  scheduler,
	}, nil
}

func (sb *StatusBar) Start() error {
	sb.mu.Lock()
	defer sb.mu.Unlock()

	if sb.running {
		return ErrStatusBarAlreadyRunning
	}

	sb.screen.Connect("monitors-changed", sb.onMonitorsChanged)

	if err := sb.createStatusBarsForAllMonitors(); err != nil {
		return fmt.Errorf("failed to create statusbar windows: %w", err)
	}

	if err := sb.loadModules(); err != nil {
		return fmt.Errorf("failed to load modules: %w", err)
	}

	if err := sb.createWidgets(); err != nil {
		return fmt.Errorf("failed to create widgets: %w", err)
	}

	if err := sb.scheduler.Start(); err != nil {
		return fmt.Errorf("failed to start scheduler: %w", err)
	}

	if err := sb.startIPCServer(); err != nil {
		log.Printf("Warning: failed to start IPC server: %v", err)
		// Don't fail the entire startup for IPC server issues
	}

	for _, window := range sb.windows {
		window.ShowAll()
	}

	sb.running = true
	sb.stopUpdate = make(chan struct{})

	log.Printf("Status bar started successfully on %d monitors", len(sb.windows))

	return nil
}

func (sb *StatusBar) createStatusBarsForAllMonitors() error {
	sb.destroyAllStatusBars()

	monitorCount := sb.display.GetNMonitors()
	if monitorCount == 0 {
		return fmt.Errorf("no monitors available")
	}

	height := sb.config.StatusBar.Height

	for i := 0; i < monitorCount; i++ {
		monitor, err := sb.display.GetMonitor(i)
		if err != nil {
			log.Printf("Warning: failed to get monitor %d: %v", i, err)
			continue
		}

		window, err := gtk.WindowNew(gtk.WINDOW_TOPLEVEL)
		if err != nil {
			return fmt.Errorf("failed to create window for monitor %d: %w", i, err)
		}

		container, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 0)
		if err != nil {
			return fmt.Errorf("failed to create container for monitor %d: %w", i, err)
		}

		window.Add(container)
		window.SetTitle(sb.config.AppName)
		window.SetName("statusbar")

		monitorGeo := monitor.GetGeometry()
		windowWidth := monitorGeo.GetWidth()

		if height > 0 {
			window.SetSizeRequest(windowWidth, height)
		}

		layer.InitForWindow(unsafe.Pointer(window.GObject))
		layer.SetAnchor(unsafe.Pointer(window.GObject), layer.EdgeLeft, true)
		layer.SetAnchor(unsafe.Pointer(window.GObject), layer.EdgeRight, true)
		layer.SetAnchor(unsafe.Pointer(window.GObject), layer.EdgeBottom, true)
		layer.SetMargin(unsafe.Pointer(window.GObject), layer.EdgeBottom, 0)
		layer.SetLayer(unsafe.Pointer(window.GObject), layer.LayerTop)
		layer.SetExclusiveZone(unsafe.Pointer(window.GObject), height)
		layer.SetKeyboardMode(unsafe.Pointer(window.GObject), layer.KeyboardModeNone)

		layer.SetMonitor(unsafe.Pointer(window.GObject), monitor)

		window.Connect("destroy", func() {
			// Only quit if we're not recreating (recreation destroys windows intentionally)
			sb.mu.Lock()
			recreating := sb.recreating
			sb.mu.Unlock()

			if !recreating {
				// Safely close the channel (don't panic if already closed)
				select {
				case <-sb.stopUpdate:
					// Channel already closed
				default:
					close(sb.stopUpdate)
				}
				sb.Quit()
			}
		})

		sb.windows[i] = window
		sb.containers[i] = container
	}

	log.Printf("Created statusbar windows for %d monitors", len(sb.windows))
	return nil
}

func (sb *StatusBar) destroyAllStatusBars() {
	for _, window := range sb.windows {
		if window != nil {
			window.Close()
		}
	}
	sb.windows = make(map[int]*gtk.Window)
	sb.containers = make(map[int]*gtk.Box)
}

type monitorWindowConfig struct {
	monitorIndex int
	monitor      *gdk.Monitor
	height       int
}

func (sb *StatusBar) onMonitorsChanged() {
	sb.mu.Lock()
	if !sb.running || sb.recreating {
		sb.mu.Unlock()
		if sb.recreating {
			log.Printf("Statusbar already recreating, skipping")
		} else {
			log.Printf("Statusbar not running, skipping recreation")
		}
		return
	}

	if sb.monitorDebounceSource != 0 {
		glib.SourceRemove(sb.monitorDebounceSource)
		sb.monitorDebounceSource = 0
	}
	sb.mu.Unlock()

	log.Printf("Monitors changed, debouncing recreation...")

	sb.mu.Lock()
	sb.monitorDebounceSource = glib.TimeoutAdd(500, func() bool {
		sb.mu.Lock()
		sb.monitorDebounceSource = 0
		if !sb.running || sb.recreating {
			sb.mu.Unlock()
			return false
		}

		if sb.monitorChangeTimerSource != 0 {
			glib.SourceRemove(sb.monitorChangeTimerSource)
			sb.monitorChangeTimerSource = 0
		}
		sb.mu.Unlock()

		log.Printf("Delaying recreation to let GDK finish processing monitor change")
		sb.mu.Lock()
		sb.monitorChangeTimerSource = glib.TimeoutAdd(1000, func() bool {
			sb.mu.Lock()
			sb.monitorChangeTimerSource = 0
			if !sb.running || sb.recreating {
				sb.mu.Unlock()
				log.Printf("Skipping recreation - statusbar not running or already recreating")
				return false
			}
			sb.mu.Unlock()
			log.Printf("Starting statusbar recreation")
			sb.recreateStatusBarsAsync()
			return false
		})
		sb.mu.Unlock()
		return false
	})
	sb.mu.Unlock()
}

func (sb *StatusBar) recreateStatusBarsAsync() {
	log.Printf("Starting statusbar recreation")

	// Set recreating flag to prevent destroy handlers from quitting app
	sb.mu.Lock()
	sb.recreating = true
	sb.mu.Unlock()

	// Pause scheduler before destroying windows
	sb.scheduler.Pause()

	// Do all recreation work in a single IdleAdd to ensure proper ordering
	// and to ensure GDK has finished processing monitor changes
	glib.IdleAdd(func() bool {
		log.Printf("Destroying old statusbars")
		sb.mu.Lock()
		sb.destroyAllStatusBars()
		sb.widgets = make(map[string]gtk.IWidget)
		sb.mu.Unlock()

		// Get monitor count after GDK has processed changes
		monitorCount := sb.display.GetNMonitors()
		log.Printf("Collecting monitor information for %d monitors", monitorCount)

		var monitorConfigs []monitorWindowConfig
		for i := 0; i < monitorCount; i++ {
			monitor, err := sb.display.GetMonitor(i)
			if err != nil {
				log.Printf("Warning: failed to get monitor %d: %v", i, err)
				continue
			}
			monitorConfigs = append(monitorConfigs, monitorWindowConfig{
				monitorIndex: i,
				monitor:      monitor,
				height:       sb.config.StatusBar.Height,
			})
		}

		log.Printf("Collected %d monitor configs, starting window creation", len(monitorConfigs))

		// Create windows for each monitor
		for _, cfg := range monitorConfigs {
			window, container, err := sb.createSingleStatusWindow(cfg)
			if err != nil {
				log.Printf("Failed to create window for monitor %d: %v", cfg.monitorIndex, err)
				continue
			}

			sb.mu.Lock()
			sb.windows[cfg.monitorIndex] = window
			sb.containers[cfg.monitorIndex] = container
			sb.mu.Unlock()

			log.Printf("Created statusbar window for monitor %d", cfg.monitorIndex)
		}

		log.Printf("Creating widgets for all monitors")
		sb.mu.Lock()
		if err := sb.createWidgets(); err != nil {
			log.Printf("Failed to recreate widgets: %v", err)
		}
		sb.mu.Unlock()

		log.Printf("Showing all statusbar windows")
		sb.mu.RLock()
		for _, window := range sb.windows {
			window.ShowAll()
		}
		sb.mu.RUnlock()

		// Clear recreating flag after everything is done
		sb.mu.Lock()
		sb.recreating = false
		sb.mu.Unlock()

		// Resume scheduler after recreation is complete
		sb.scheduler.Resume()

		log.Printf("Statusbar recreation completed")
		return false
	})
}

func (sb *StatusBar) createSingleStatusWindow(cfg monitorWindowConfig) (*gtk.Window, *gtk.Box, error) {
	window, err := gtk.WindowNew(gtk.WINDOW_TOPLEVEL)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to create window: %w", err)
	}

	container, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 0)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to create container: %w", err)
	}

	window.Add(container)
	window.SetTitle(sb.config.AppName)
	window.SetName("statusbar")

	monitorGeo := cfg.monitor.GetGeometry()
	windowWidth := monitorGeo.GetWidth()

	if cfg.height > 0 {
		window.SetSizeRequest(windowWidth, cfg.height)
	}

	layer.InitForWindow(unsafe.Pointer(window.GObject))
	layer.SetAnchor(unsafe.Pointer(window.GObject), layer.EdgeLeft, true)
	layer.SetAnchor(unsafe.Pointer(window.GObject), layer.EdgeRight, true)
	layer.SetAnchor(unsafe.Pointer(window.GObject), layer.EdgeBottom, true)
	layer.SetMargin(unsafe.Pointer(window.GObject), layer.EdgeBottom, 0)
	layer.SetLayer(unsafe.Pointer(window.GObject), layer.LayerTop)
	layer.SetExclusiveZone(unsafe.Pointer(window.GObject), cfg.height)
	layer.SetKeyboardMode(unsafe.Pointer(window.GObject), layer.KeyboardModeNone)
	layer.SetMonitor(unsafe.Pointer(window.GObject), cfg.monitor)

	window.Connect("destroy", func() {
		close(sb.stopUpdate)
		sb.Quit()
	})

	return window, container, nil
}

func (sb *StatusBar) Stop() error {
	sb.mu.Lock()
	defer sb.mu.Unlock()

	if !sb.running {
		return nil
	}

	if sb.monitorDebounceSource != 0 {
		glib.SourceRemove(sb.monitorDebounceSource)
		sb.monitorDebounceSource = 0
	}

	if sb.monitorChangeTimerSource != 0 {
		glib.SourceRemove(sb.monitorChangeTimerSource)
		sb.monitorChangeTimerSource = 0
	}

	sb.scheduler.Stop()
	sb.registry.CleanupAll()
	sb.stopIPCServer()

	for _, window := range sb.windows {
		if window != nil {
			window.Close()
		}
	}

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
	log.Printf("[STATUSBAR] Received IPC message: %s", msg)
	scheduledModules := sb.scheduler.GetScheduledModules()
	log.Printf("[STATUSBAR] Scheduled modules: %v", scheduledModules)
	handled := sb.scheduler.HandleIPCMessage(msg)
	log.Printf("[STATUSBAR] IPC message handled: %v", handled)
	return nil
}

func (sb *StatusBar) loadModules() error {
	allModules := append(append(sb.config.StatusBar.Layout.Left, sb.config.StatusBar.Layout.Middle...), sb.config.StatusBar.Layout.Right...)
	log.Printf("Loading modules, config: %v", allModules)

	for _, moduleName := range allModules {
		moduleConfig := sb.config.StatusBar.ModuleConfigs[moduleName]
		log.Printf("Loading module '%s' with config: %v", moduleName, moduleConfig)

		var module statusbar.Module
		var err error

		if moduleName == "launcher" {
			launcherFactory := statusbarModules.NewLauncherModuleFactory(sb.app)
			module, err = launcherFactory.CreateModule(moduleConfig.ToMap())
			if err != nil {
				log.Printf("Failed to create launcher module: %v", err)
				continue
			}
			if err := sb.registry.RegisterModule(module); err != nil {
				log.Printf("Failed to register launcher module: %v", err)
				continue
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

		log.Printf("Successfully loaded module: %s", moduleName)
	}

	return nil
}

func (sb *StatusBar) createWidgets() error {
	sb.widgets = make(map[string]gtk.IWidget)

	for monitorIndex, container := range sb.containers {
		if err := sb.createWidgetsForContainer(container, monitorIndex); err != nil {
			return fmt.Errorf("failed to create widgets for monitor %d: %w", monitorIndex, err)
		}
	}

	return nil
}

func (sb *StatusBar) createWidgetsForContainer(container *gtk.Box, monitorIndex int) error {
	leftBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 0)
	if err != nil {
		return fmt.Errorf("failed to create left box: %w", err)
	}

	middleBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 0)
	if err != nil {
		return fmt.Errorf("failed to create middle box: %w", err)
	}

	rightBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 0)
	if err != nil {
		return fmt.Errorf("failed to create right box: %w", err)
	}

	leftSpacer, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 0)
	if err != nil {
		return fmt.Errorf("failed to create left spacer: %w", err)
	}
	leftSpacer.SetHExpand(true)

	rightSpacer, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 0)
	if err != nil {
		return fmt.Errorf("failed to create right spacer: %w", err)
	}
	rightSpacer.SetHExpand(true)

	if err := sb.constructSection(sb.config.StatusBar.Layout.Left, leftBox); err != nil {
		return fmt.Errorf("failed to construct left section: %w", err)
	}

	if err := sb.constructSection(sb.config.StatusBar.Layout.Middle, middleBox); err != nil {
		return fmt.Errorf("failed to construct middle section: %w", err)
	}

	if err := sb.constructSection(sb.config.StatusBar.Layout.Right, rightBox); err != nil {
		return fmt.Errorf("failed to construct right section: %w", err)
	}

	container.PackStart(leftBox, false, false, 0)
	container.PackStart(leftSpacer, false, false, 0)
	container.PackStart(middleBox, false, false, 0)
	container.PackStart(rightSpacer, false, false, 0)
	container.PackStart(rightBox, false, false, 0)

	return nil
}

func (sb *StatusBar) constructSection(modules []string, box *gtk.Box) error {
	for i, moduleName := range modules {
		if i > 0 {
			sep, err := gtk.LabelNew(" | ")
			if err != nil {
				log.Printf("Failed to create separator: %v", err)
				continue
			}
			if ctx, err := sep.GetStyleContext(); err == nil {
				ctx.AddClass("separator")
			}
			box.PackStart(sep, false, false, 0)
		}

		// Check if module was successfully loaded and registered
		if _, exists := sb.registry.GetModule(moduleName); !exists {
			log.Printf("Module '%s' was not loaded, creating error widget", moduleName)
			// Create error widget as fallback
			errorWidget, err := gtk.LabelNew(fmt.Sprintf("[%s]", moduleName))
			if err != nil {
				log.Printf("Failed to create error widget for module '%s': %v", moduleName, err)
				continue
			}
			box.PackStart(errorWidget, false, false, 0)
			continue
		}

		log.Printf("Creating widget for module: %s", moduleName)
		widget, err := sb.registry.CreateWidgetForModule(moduleName)
		if err != nil {
			log.Printf("Failed to create widget for module '%s': %v", moduleName, err)
			// Create error widget as fallback
			errorWidget, err := gtk.LabelNew(fmt.Sprintf("[%s]", moduleName))
			if err != nil {
				log.Printf("Failed to create error widget: %v", err)
				continue
			}
			box.PackStart(errorWidget, false, false, 0)
			continue
		}

		if err := sb.scheduler.ScheduleModule(moduleName, widget); err != nil {
			log.Printf("Failed to schedule module '%s': %v", moduleName, err)
		}

		sb.widgets[moduleName] = widget
		box.PackStart(widget, false, false, 0)

		log.Printf("Successfully created widget for module: %s", moduleName)
	}

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

// Hide hides all statusbar windows
func (sb *StatusBar) Hide() {
	sb.mu.Lock()
	defer sb.mu.Unlock()
	for _, window := range sb.windows {
		if window != nil {
			window.Hide()
		}
	}
}

// Show shows all statusbar windows
func (sb *StatusBar) Show() {
	sb.mu.Lock()
	defer sb.mu.Unlock()
	for _, window := range sb.windows {
		if window != nil {
			window.ShowAll()
		}
	}
}

// startIPCServer starts the IPC socket server for external communication
func (sb *StatusBar) startIPCServer() error {
	sb.ipcSocket = sb.config.SocketPath
	if sb.ipcSocket == "" {
		sb.ipcSocket = "/tmp/locus_socket"
	}

	// Remove existing socket if it exists
	if _, err := os.Stat(sb.ipcSocket); err == nil {
		os.Remove(sb.ipcSocket)
	}

	listener, err := net.Listen("unix", sb.ipcSocket)
	if err != nil {
		return fmt.Errorf("failed to start IPC server: %w", err)
	}

	sb.ipcListener = listener
	sb.ipcRunning = true

	// Start IPC server loop in a goroutine
	go sb.ipcServerLoop()

	log.Printf("IPC server started on %s", sb.ipcSocket)
	return nil
}

// stopIPCServer stops the IPC socket server
func (sb *StatusBar) stopIPCServer() {
	sb.ipcRunning = false
	if sb.ipcListener != nil {
		sb.ipcListener.Close()
	}
	if _, err := os.Stat(sb.ipcSocket); err == nil {
		os.Remove(sb.ipcSocket)
	}
	log.Printf("IPC server stopped")
}

// ipcServerLoop handles incoming IPC connections
func (sb *StatusBar) ipcServerLoop() {
	defer sb.ipcListener.Close()

	for sb.ipcRunning {
		conn, err := sb.ipcListener.Accept()
		if err != nil {
			if sb.ipcRunning {
				log.Printf("IPC server accept error: %v", err)
			}
			break
		}

		go sb.handleIPCConnection(conn)
	}
}

// handleIPCConnection processes a single IPC connection
func (sb *StatusBar) handleIPCConnection(conn net.Conn) {
	defer conn.Close()

	// Read the message
	buffer := make([]byte, 1024)
	n, err := conn.Read(buffer)
	if err != nil {
		log.Printf("IPC read error: %v", err)
		return
	}

	message := strings.TrimSpace(string(buffer[:n]))
	if message == "" {
		return
	}

	log.Printf("Received IPC message: %s", message)

	// Handle the message
	handled := sb.handleIPCMessage(message)
	if !handled {
		log.Printf("Unhandled IPC message: %s", message)
	}
}

// handleIPCMessage processes IPC messages and returns true if handled
func (sb *StatusBar) handleIPCMessage(message string) bool {
	switch {
	case message == "launcher":
		// Show launcher
		glib.IdleAdd(func() bool {
			sb.app.PresentLauncher()
			return false
		})
		return true

	case message == "lock":
		// Show lockscreen
		glib.IdleAdd(func() bool {
			if err := sb.app.ShowLockScreen(); err != nil {
				log.Printf("Failed to show lock screen: %v", err)
			}
			return false
		})
		return true

	case strings.HasPrefix(message, "launcher:"):
		// Handle launcher subcommands
		cmd := strings.TrimPrefix(message, "launcher:")
		switch cmd {
		case "resume":
			// TODO: Implement resume functionality when launcher supports state
			glib.IdleAdd(func() bool {
				sb.app.PresentLauncher()
				return false
			})
			return true
		case "fresh":
			// TODO: Implement fresh start when launcher supports clearing state
			glib.IdleAdd(func() bool {
				sb.app.PresentLauncher()
				return false
			})
			return true
		}

	case strings.HasPrefix(message, "launcher dmenu:"):
		// Handle dmenu with options - for now just show launcher
		// TODO: Implement dmenu options when launcher supports it
		glib.IdleAdd(func() bool {
			sb.app.PresentLauncher()
			return false
		})
		return true

	case strings.HasPrefix(message, ">") || strings.HasPrefix(message, "launcher "):
		// Handle launcher commands - for now just show launcher
		// TODO: Implement direct command input when launcher supports it
		glib.IdleAdd(func() bool {
			sb.app.PresentLauncher()
			return false
		})
		return true

	case strings.HasPrefix(message, "status:"):
		// Handle status messages
		statusMsg := strings.TrimPrefix(message, "status:")
		glib.IdleAdd(func() bool {
			sb.sendStatusMessage(statusMsg)
			return false
		})
		return true

	default:
		// Try to handle through modules
		return sb.scheduler.HandleIPCMessage(message)
	}

	return false
}

// sendStatusMessage sends a status message to the custom_message module
func (sb *StatusBar) sendStatusMessage(message string) {
	sb.scheduler.HandleIPCMessage(fmt.Sprintf("custom_message:%s", message))
}
