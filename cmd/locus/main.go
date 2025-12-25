package main

import (
	"log"
	"os"

	"github.com/sigma/locus-go/internal/config"
	"github.com/sigma/locus-go/internal/core"
)

func main() {
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
