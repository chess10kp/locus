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
	cfg, err := config.LoadConfig(configPath)
	if err != nil {
		log.Printf("Failed to load config: %v", err)
		cfg = &config.DefaultConfig
	}

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
