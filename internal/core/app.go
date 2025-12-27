package core

import (
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/gotk3/gotk3/gtk"
	"github.com/chess10kp/locus/internal/config"
	"github.com/chess10kp/locus/internal/lockscreen"
	"github.com/chess10kp/locus/internal/notification"
)

// App is main application
type App struct {
	config          *config.Config
	running         bool
	sigChan         chan os.Signal
	statusBar       *StatusBar
	launcher        *Launcher
	ipc             *IPCServer
	lockscreen      *lockscreen.LockScreenManager
	notificationMgr *notification.Manager
}

// NewApp creates a new application
func NewApp(cfg *config.Config) (*App, error) {
	return &App{
		config:  cfg,
		running: false,
		sigChan: make(chan os.Signal, 1),
	}, nil
}

// Run starts the application
func (a *App) Run() error {
	a.running = true

	// Handle system signals
	signal.Notify(a.sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		sig := <-a.sigChan
		log.Printf("Received signal: %v", sig)
		a.Quit()
	}()

	log.Println("Locus starting...")

	// Run main loop
	return a.runMainLoop()
}

// runMainLoop runs the main application loop
func (a *App) runMainLoop() error {
	// Initialize components
	a.initialize()

	// Start GTK main loop
	gtk.Main()

	return nil
}

// initialize initializes all components
func (a *App) initialize() {
	log.Println("Initializing components...")

	gtk.Init(nil)
	SetupStyles()

	a.lockscreen = lockscreen.NewLockScreenManager(a.config)

	if a.config.Notification.Daemon.Enabled {
		notificationMgr, err := notification.NewManager(&a.config.Notification)
		if err != nil {
			log.Printf("Failed to create notification manager: %v", err)
		} else {
			a.notificationMgr = notificationMgr
			if err := notificationMgr.Start(); err != nil {
				log.Printf("Failed to start notification manager: %v", err)
			} else {
				log.Println("Notification manager started")
			}
		}
	}

	// Create status bar
	sb, err := NewStatusBar(a, a.config)
	if err != nil {
		log.Printf("Failed to create status bar: %v", err)
	} else {
		a.statusBar = sb
		if err := sb.Start(); err != nil {
			log.Printf("Failed to start status bar: %v", err)
		}
	}

	// Create launcher
	l, err := NewLauncher(a, a.config)
	if err != nil {
		log.Printf("Failed to create launcher: %v", err)
	} else {
		a.launcher = l
	}

	// Start IPC server
	ipc := NewIPCServer(a, a.config)
	if err := ipc.Start(); err != nil {
		log.Printf("Failed to start IPC server: %v", err)
	} else {
		a.ipc = ipc
	}

	log.Println("Initialization complete")
}

// Quit gracefully quits the application
func (a *App) Quit() {
	if !a.running {
		return
	}
	a.running = false

	log.Println("Shutting down...")

	// Clean up
	if a.lockscreen != nil {
		a.lockscreen.Cleanup()
	}

	if a.notificationMgr != nil {
		a.notificationMgr.Stop()
	}

	if a.statusBar != nil {
		a.statusBar.Stop()
	}

	if a.launcher != nil {
		a.launcher.Stop()
	}

	if a.ipc != nil {
		a.ipc.Stop()
	}

	// Quit GTK main loop
	gtk.MainQuit()
}

// PresentLauncher shows the launcher
func (a *App) PresentLauncher() error {
	log.Printf("PresentLauncher called, launcher=%v", a.launcher != nil)
	if a.launcher != nil {
		err := a.launcher.Show()
		log.Printf("Launcher.Show() returned: %v", err)
		return err
	}
	log.Printf("No launcher available")
	return nil
}

// HideLauncher hides the launcher
func (a *App) HideLauncher() error {
	if a.launcher != nil {
		a.launcher.Hide()
		return nil
	}
	return nil
}

// GetConfig returns the application config
func (a *App) GetConfig() *config.Config {
	return a.config
}

// ShowLockScreen shows the lock screen
func (a *App) ShowLockScreen() error {
	if a.lockscreen == nil {
		return nil
	}
	return a.lockscreen.Show()
}

// HideLockScreen hides the lock screen
func (a *App) HideLockScreen() error {
	if a.lockscreen == nil {
		return nil
	}
	return a.lockscreen.Hide()
}

// IsLocked returns whether the lock screen is active
func (a *App) IsLocked() bool {
	if a.lockscreen == nil {
		return false
	}
	return a.lockscreen.IsLocked()
}
