package main

import (
	"fmt"
	"os"

	"github.com/chess10kp/locus/internal/config"
)

func main() {
	configPath := "~/.config/locus/config.toml"
	if len(os.Args) > 1 {
		configPath = os.Args[1]
	}

	fmt.Printf("Validating config: %s\n", configPath)

	if err := config.ValidateConfig(configPath); err != nil {
		fmt.Printf("❌ Config validation failed: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("✅ Config is valid!")
}
