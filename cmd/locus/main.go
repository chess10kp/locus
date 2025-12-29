package main

import (
	"io/ioutil"
	"log"
	"os"
	"strconv"
	"syscall"

	"github.com/chess10kp/locus/internal/config"
	"github.com/chess10kp/locus/internal/core"
)

const pidFile = "/tmp/locus.pid"

func ensureSingleInstance() error {
	if data, err := ioutil.ReadFile(pidFile); err == nil {
		if pid, err := strconv.Atoi(string(data)); err == nil {
			process, err := os.FindProcess(pid)
			if err == nil {
				// Check if process is still running
				if err := process.Signal(syscall.Signal(0)); err == nil {
					// Kill the process
					process.Kill()
					process.Wait()
				}
			}
		}
	}
	currentPid := os.Getpid()
	return ioutil.WriteFile(pidFile, []byte(strconv.Itoa(currentPid)), 0644)
}

func cleanup() {
	os.Remove(pidFile)
}

func main() {
	// Set up logging to file
	logFile, err := os.OpenFile("locus.log", os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
	if err == nil {
		log.SetOutput(logFile)
		defer logFile.Close()
	}

	// Ensure single instance
	if err := ensureSingleInstance(); err != nil {
		log.Fatalf("Failed to ensure single instance: %v", err)
	}
	defer cleanup()

	// Load configuration
	configPath := "~/.config/locus/config.toml"
	if len(os.Args) > 2 && os.Args[1] == "--config" {
		configPath = os.Args[2]
	}
	log.Printf("Attempting to load config from: %s", configPath)
	cfg, err := config.LoadConfig(configPath)
	if err != nil {
		log.Printf("Failed to load config: %v", err)
		cfg = &config.DefaultConfig
		log.Printf("Using default config, notification daemon enabled: %v", cfg.Notification.Daemon.Enabled)
	} else {
		log.Printf("Config loaded successfully, notification daemon enabled: %v", cfg.Notification.Daemon.Enabled)
		log.Printf("Config loaded successfully, notifications in layout: %v", cfg.StatusBar.Layout.Right)
		log.Printf("Animation config - Enabled: %v, FadeEnabled: %v, ScaleEnabled: %v",
			cfg.Launcher.Animation.Enabled, cfg.Launcher.Animation.FadeEnabled, cfg.Launcher.Animation.ScaleEnabled)
	}

	log.Printf("Config values - Daemon.Enabled: %v", cfg.Notification.Daemon.Enabled)
	log.Printf("Config values - Daemon.Position: %s", cfg.Notification.Daemon.Position)

	// Create application
	app, err := core.NewApp(cfg)
	if err != nil {
		log.Fatalf("Failed to create application: %v", err)
	}

	// Run application
	if err := app.Run(); err != nil {
		log.Fatalf("Application error: %v", err)
	}

	os.Exit(0)
}
