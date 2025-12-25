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
	window      *gtk.Window
	container   *gtk.Box
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
	sb.window.SetName("statusbar")

	height := sb.config.StatusBar.Height
	if height > 0 {
		sb.window.SetSizeRequest(-1, height)
		log.Printf("Setting size request to -1, %d", height)
	}

	// Initialize layer shell
	layer.InitForWindow(unsafe.Pointer(sb.window.GObject))
	layer.SetAnchor(unsafe.Pointer(sb.window.GObject), layer.EdgeLeft, true)
	layer.SetAnchor(unsafe.Pointer(sb.window.GObject), layer.EdgeRight, true)
	layer.SetAnchor(unsafe.Pointer(sb.window.GObject), layer.EdgeTop, true)
	layer.SetMargin(unsafe.Pointer(sb.window.GObject), layer.EdgeTop, 0)
	layer.SetLayer(unsafe.Pointer(sb.window.GObject), layer.LayerTop)
	layer.SetExclusiveZone(unsafe.Pointer(sb.window.GObject), height)
	layer.SetKeyboardMode(unsafe.Pointer(sb.window.GObject), layer.KeyboardModeNone)
	log.Printf("LayerShell configured")

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
	sb.stopIPCServer()
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
	leftSpacer, err := gtk.LabelNew("")
	if err != nil {
		return fmt.Errorf("failed to create left spacer: %w", err)
	}
	leftSpacer.SetHExpand(true)
	leftSpacer.SetHAlign(gtk.ALIGN_FILL)

	rightSpacer, err := gtk.LabelNew("")
	if err != nil {
		return fmt.Errorf("failed to create right spacer: %w", err)
	}
	rightSpacer.SetHExpand(true)
	rightSpacer.SetHAlign(gtk.ALIGN_FILL)

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
	sb.container.PackStart(leftBox, false, false, 0)
	sb.container.PackStart(leftSpacer, false, false, 0)
	sb.container.PackStart(middleBox, false, false, 0)
	sb.container.PackStart(rightSpacer, false, false, 0)
	sb.container.PackStart(rightBox, false, false, 0)

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
		sb.app.PresentLauncher()
		return true

	case strings.HasPrefix(message, "launcher:"):
		// Handle launcher subcommands
		cmd := strings.TrimPrefix(message, "launcher:")
		switch cmd {
		case "resume":
			// TODO: Implement resume functionality when launcher supports state
			sb.app.PresentLauncher()
			return true
		case "fresh":
			// TODO: Implement fresh start when launcher supports clearing state
			sb.app.PresentLauncher()
			return true
		}

	case strings.HasPrefix(message, "launcher dmenu:"):
		// Handle dmenu with options - for now just show launcher
		// TODO: Implement dmenu options when launcher supports it
		sb.app.PresentLauncher()
		return true

	case strings.HasPrefix(message, ">") || strings.HasPrefix(message, "launcher "):
		// Handle launcher commands - for now just show launcher
		// TODO: Implement direct command input when launcher supports it
		sb.app.PresentLauncher()
		return true

	case strings.HasPrefix(message, "status:"):
		// Handle status messages
		statusMsg := strings.TrimPrefix(message, "status:")
		sb.sendStatusMessage(statusMsg)
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
