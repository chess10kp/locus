package core

import (
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/sigma/locus-go/internal/config"
)

// App is main application
type App struct {
	config    *config.Config
	running   bool
	sigChan   chan os.Signal
	statusBar *StatusBar
	launcher  *Launcher
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

	// Simple event loop
	for a.running {
		time.Sleep(100 * time.Millisecond)
	}

	return nil
}

// initialize initializes all components
func (a *App) initialize() {
	log.Println("Initializing components...")

	// Create status bar
	sb, err := NewStatusBar(a.config)
	if err != nil {
		log.Printf("Failed to create status bar: %v", err)
	} else {
		a.statusBar = sb
		sb.Show()
	}

	// Create launcher
	l, err := NewLauncher(a.config)
	if err != nil {
		log.Printf("Failed to create launcher: %v", err)
	} else {
		a.launcher = l
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
	if a.statusBar != nil {
		a.statusBar.Cleanup()
	}

	if a.launcher != nil {
		a.launcher.Cleanup()
	}
}

// PresentLauncher shows the launcher
func (a *App) PresentLauncher() {
	if a.launcher != nil {
		a.launcher.Present()
	}
}

// HideLauncher hides the launcher
func (a *App) HideLauncher() {
	if a.launcher != nil {
		a.launcher.Hide()
	}
}

// GetConfig returns the application config
func (a *App) GetConfig() *config.Config {
	return a.config
}
