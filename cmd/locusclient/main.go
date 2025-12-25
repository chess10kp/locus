package main

import (
	"fmt"
	"log"
	"net"
	"os"
	"path/filepath"

	"github.com/sigma/locus-go/internal/config"
)

var (
	socketPath = config.DefaultConfig.SocketPath
)

func init() {
	// Try to load config to get custom socket path
	configPath := filepath.Join(os.Getenv("HOME"), ".config", "locus", "config.toml")
	cfg, err := config.LoadConfig(configPath)
	if err == nil && cfg.SocketPath != "" {
		socketPath = cfg.SocketPath
	}
}

func main() {
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	command := os.Args[1]

	switch command {
	case "launcher":
		sendMessage("launcher")
	case "hide":
		sendMessage("hide")
	case "statusbar":
		if len(os.Args) < 3 {
			printUsage()
			os.Exit(1)
		}
		sendMessage("statusbar:" + os.Args[2])
	case "help", "-h", "--help":
		printUsage()
	default:
		// Send raw message
		sendMessage(command)
	}
}

func sendMessage(message string) {
	conn, err := net.Dial("unix", socketPath)
	if err != nil {
		log.Fatalf("Failed to connect to locus socket: %v\nIs locus running?", err)
	}
	defer conn.Close()

	_, err = conn.Write([]byte(message))
	if err != nil {
		log.Fatalf("Failed to send message: %v", err)
	}

	log.Printf("Sent: %s", message)
}

func printUsage() {
	fmt.Println("locusclient - Control Locus from command line")
	fmt.Println()
	fmt.Println("Usage: locusclient <command> [args]")
	fmt.Println()
	fmt.Println("Commands:")
	fmt.Println("  launcher    Show the application launcher")
	fmt.Println("  hide        Hide the application launcher")
	fmt.Println("  statusbar <msg>  Send message to status bar")
	fmt.Println("  help        Show this help message")
	fmt.Println()
	fmt.Println("Examples:")
	fmt.Println("  locusclient launcher           # Show launcher (bind to a key)")
	fmt.Println("  locusclient hide               # Hide launcher")
	fmt.Println("  locusclient statusbar \"Hello\"  # Display message on status bar")
	fmt.Println()
	fmt.Println("Socket path:", socketPath)
}
