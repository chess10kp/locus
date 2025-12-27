package core

import (
	"errors"
	"fmt"
	"log"
	"net"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"unsafe"

	"github.com/gotk3/gotk3/gdk"
	"github.com/gotk3/gotk3/glib"
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
	app         *App
	config      *config.Config
	windows     map[int]*gtk.Window // Map: monitor index -> window
	containers  map[int]*gtk.Box    // Map: monitor index -> container
	screen      *gdk.Screen         // GDK screen for monitor tracking
	registry    *statusbar.ModuleRegistry
	scheduler   *statusbar.UpdateScheduler
	widgets     map[string]gtk.IWidget
	running     bool
	stopUpdate  chan struct{}
	ipcRunning  bool
	ipcListener net.Listener
	ipcSocket   string
	mu          sync.RWMutex
}

func NewStatusBar(app *App, cfg *config.Config) (*StatusBar, error) {
	// Get default screen for monitor tracking
	screen, err := gdk.ScreenGetDefault()
	if err != nil {
		return nil, fmt.Errorf("failed to get default screen: %w", err)
	}

	registry := statusbar.DefaultRegistry()
	scheduler := statusbar.NewUpdateScheduler(registry)

	return &StatusBar{
		app:        app,
		config:     cfg,
		windows:    make(map[int]*gtk.Window),
		containers: make(map[int]*gtk.Box),
		screen:     screen,
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

	// Set up monitor change signal handler
	sb.screen.Connect("monitors-changed", sb.onMonitorsChanged)

	// Create statusbar windows for all current monitors
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

	// Start IPC server
	if err := sb.startIPCServer(); err != nil {
		log.Printf("Warning: failed to start IPC server: %v", err)
		// Don't fail the entire startup for IPC server issues
	}

	// Show all statusbar windows
	for _, window := range sb.windows {
		window.ShowAll()
	}

	sb.running = true
	sb.stopUpdate = make(chan struct{})

	log.Printf("Status bar started successfully on %d monitors", len(sb.windows))

	return nil
}

// createStatusBarsForAllMonitors creates statusbar windows for all current monitors
func (sb *StatusBar) createStatusBarsForAllMonitors() error {
	// Destroy existing windows if any
	sb.destroyAllStatusBars()

	// Get monitor count using xrandr
	cmd := exec.Command("sh", "-c", "xrandr --listmonitors 2>/dev/null | grep Monitors: | awk '{print $2}' || echo 1")
	output, err := cmd.Output()
	monitorCount := 1 // default
	if err != nil {
		log.Printf("Warning: failed to get monitor count, assuming 1: %v", err)
	} else {
		countStr := strings.TrimSpace(string(output))
		if count, err := strconv.Atoi(countStr); err == nil && count > 0 {
			monitorCount = count
		}
	}

	if monitorCount == 0 {
		return fmt.Errorf("no monitors available")
	}

	height := sb.config.StatusBar.Height

	// Create statusbar for each monitor
	for i := 0; i < monitorCount; i++ {
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

		if height > 0 {
			window.SetSizeRequest(-1, height)
		}

		// Initialize layer shell for this monitor
		layer.InitForWindow(unsafe.Pointer(window.GObject))
		layer.SetAnchor(unsafe.Pointer(window.GObject), layer.EdgeLeft, true)
		layer.SetAnchor(unsafe.Pointer(window.GObject), layer.EdgeRight, true)
		layer.SetAnchor(unsafe.Pointer(window.GObject), layer.EdgeTop, true)
		layer.SetMargin(unsafe.Pointer(window.GObject), layer.EdgeTop, 0)
		layer.SetLayer(unsafe.Pointer(window.GObject), layer.LayerTop)
		layer.SetExclusiveZone(unsafe.Pointer(window.GObject), height)
		layer.SetKeyboardMode(unsafe.Pointer(window.GObject), layer.KeyboardModeNone)

		// Connect destroy signal to quit
		window.Connect("destroy", func() {
			close(sb.stopUpdate)
			sb.Quit()
		})

		sb.windows[i] = window
		sb.containers[i] = container
	}

	log.Printf("Created statusbar windows for %d monitors", monitorCount)
	return nil
}

// destroyAllStatusBars destroys all statusbar windows
func (sb *StatusBar) destroyAllStatusBars() {
	for _, window := range sb.windows {
		if window != nil {
			window.Destroy()
		}
	}
	sb.windows = make(map[int]*gtk.Window)
	sb.containers = make(map[int]*gtk.Box)
}

// onMonitorsChanged handles monitor configuration changes
func (sb *StatusBar) onMonitorsChanged() {
	log.Printf("Monitors changed, recreating statusbar windows")
	// Recreate all statusbars from scratch as requested
	if err := sb.createStatusBarsForAllMonitors(); err != nil {
		log.Printf("Failed to recreate statusbar windows: %v", err)
		return
	}

	// Recreate widgets for all monitors
	if err := sb.createWidgets(); err != nil {
		log.Printf("Failed to recreate widgets: %v", err)
		return
	}

	// Show all windows
	for _, window := range sb.windows {
		window.ShowAll()
	}
}

func (sb *StatusBar) Stop() error {
	sb.mu.Lock()
	defer sb.mu.Unlock()

	if !sb.running {
		return nil
	}

	sb.scheduler.Stop()
	sb.registry.CleanupAll()
	sb.stopIPCServer()

	// Close all windows
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
	handled := sb.scheduler.HandleIPCMessage(msg)
	log.Printf("[STATUSBAR] IPC message handled: %v", handled)
	return nil
}

func (sb *StatusBar) loadModules() error {
	// Collect all modules from all sections
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

	// Create widget tree for each monitor's container
	for monitorIndex, container := range sb.containers {
		if err := sb.createWidgetsForContainer(container, monitorIndex); err != nil {
			return fmt.Errorf("failed to create widgets for monitor %d: %w", monitorIndex, err)
		}
	}

	return nil
}

func (sb *StatusBar) createWidgetsForContainer(container *gtk.Box, monitorIndex int) error {
	// Create section containers
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

	// Create spacers for centering middle section
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

	// Build sections
	if err := sb.constructSection(sb.config.StatusBar.Layout.Left, leftBox); err != nil {
		return fmt.Errorf("failed to construct left section: %w", err)
	}

	if err := sb.constructSection(sb.config.StatusBar.Layout.Middle, middleBox); err != nil {
		return fmt.Errorf("failed to construct middle section: %w", err)
	}

	if err := sb.constructSection(sb.config.StatusBar.Layout.Right, rightBox); err != nil {
		return fmt.Errorf("failed to construct right section: %w", err)
	}

	// Assemble main container
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
			// Add separator between modules
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
