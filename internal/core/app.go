package core

import (
	"log"
	"os"
	"os/signal"
	"runtime"
	"syscall"
	"time"

	"github.com/chess10kp/locus/internal/config"
	"github.com/chess10kp/locus/internal/launcher"
	"github.com/chess10kp/locus/internal/lockscreen"
	"github.com/gotk3/gotk3/glib"
	"github.com/gotk3/gotk3/gtk"
)

// App is main application
type App struct {
	config     *config.Config
	running    bool
	sigChan    chan os.Signal
	statusBar  *StatusBar
	launcher   *Launcher
	ipc        *IPCServer
	lockscreen *lockscreen.LockScreenManager
	iconCache  *launcher.IconCache
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

	currentTheme, exists := a.config.Theme.Themes[a.config.Theme.CurrentTheme]
	if !exists {
		log.Printf("Theme '%s' not found, using default", a.config.Theme.CurrentTheme)
		currentTheme = config.DefaultTheme()
	}

	SetupThemeEngine(&currentTheme)
	SetupStylesWithTheme()
	SetupStatusBarStylesWithTheme()
	SetupLauncherStylesWithTheme()
	SetupLockscreenStylesWithTheme()

	log.Printf("Applied theme: %s", a.config.Theme.CurrentTheme)

	// Add GTK main loop monitoring
	go a.monitorGTKMainLoop()

	a.lockscreen = lockscreen.NewLockScreenManager(a.config)

	iconCache, err := launcher.NewIconCache(a.config)
	if err != nil {
		log.Printf("Failed to create icon cache: %v", err)
		iconCache = nil
	}
	a.iconCache = iconCache

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
	if a.launcher == nil {
		log.Printf("PresentLauncher: launcher is nil!")
		return nil
	}
	err := a.launcher.Show()
	log.Printf("Launcher.Show() returned: %v", err)
	return err
}

// HideLauncher hides the launcher
func (a *App) HideLauncher() error {
	if a.launcher != nil {
		a.launcher.Hide()
		return nil
	}
	return nil
}

// ToggleLauncher toggles the launcher visibility
func (a *App) ToggleLauncher() error {
	if a.launcher == nil {
		log.Printf("ToggleLauncher: launcher is nil!")
		return nil
	}
	err := a.launcher.Toggle()
	log.Printf("Launcher.Toggle() returned: %v", err)
	return err
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
	if a.statusBar != nil {
		a.statusBar.Hide()
	}
	return a.lockscreen.Show()
}

// HideLockScreen hides the lock screen
func (a *App) HideLockScreen() error {
	if a.lockscreen == nil {
		return nil
	}
	if a.statusBar != nil {
		a.statusBar.Show()
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

// monitorGTKMainLoop monitors the GTK main loop for blockages
func (a *App) monitorGTKMainLoop() {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		var m runtime.MemStats
		runtime.ReadMemStats(&m)
		log.Printf("[MONITOR] Goroutines: %d, Alloc: %d MB, HeapObjects: %d",
			runtime.NumGoroutine(), m.Alloc/1024/1024, m.HeapObjects)

		// Try to queue a callback to detect if GTK main loop is responsive
		testStart := time.Now()
		testDone := make(chan bool, 1)
		glib.IdleAdd(func() {
			testDone <- true
		})

		select {
		case <-testDone:
			waitTime := time.Since(testStart)
			log.Printf("[MONITOR] GTK main loop responsive (callback executed in %v)", waitTime)
			if waitTime > 1*time.Second {
				log.Printf("[MONITOR] WARNING: Callback took %v to execute - some blocking operation may be running", waitTime)
			}
		case <-time.After(2 * time.Second):
			waitTime := time.Since(testStart)
			log.Printf("[MONITOR] WARNING: GTK main loop appears to be BLOCKED (callback not executed in %v)", waitTime)

			// Additional diagnostic: try with multiple timeouts to estimate how long it's been blocked
			for i := 1; i <= 4; i++ {
				testStart2 := time.Now()
				testDone2 := make(chan bool, 1)
				glib.IdleAdd(func() {
					testDone2 <- true
				})
				select {
				case <-testDone2:
					log.Printf("[MONITOR] Callback executed on attempt %d after %v from first attempt",
						i+1, time.Since(testStart2)+time.Duration(i)*2*time.Second)
					break
				case <-time.After(2 * time.Second):
					log.Printf("[MONITOR] Callback still not executing on attempt %d (%v from first attempt)",
						i+1, time.Since(testStart))
				}
			}
		}
	}
}
