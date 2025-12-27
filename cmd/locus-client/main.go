package main

import (
	"bufio"
	"fmt"
	"net"
	"os"
	"os/exec"
	"strconv"
	"strings"
)

const defaultSocketPath = "/tmp/locus_socket"

func hasCommand(cmd string) bool {
	_, err := exec.LookPath(cmd)
	return err == nil
}

func runCommand(cmd string) string {
	parts := strings.Fields(cmd)
	if len(parts) == 0 {
		return ""
	}

	command := exec.Command(parts[0], parts[1:]...)
	output, err := command.Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(output))
}

func sendMessage(message string) error {
	socketPath := os.Getenv("LOCUS_SOCKET")
	if socketPath == "" {
		socketPath = defaultSocketPath
	}

	conn, err := net.Dial("unix", socketPath)
	if err != nil {
		return fmt.Errorf("failed to connect to locus socket: %w", err)
	}
	defer conn.Close()

	_, err = conn.Write([]byte(message))
	if err != nil {
		return fmt.Errorf("failed to send message: %w", err)
	}

	return nil
}

func handleVolume(action string) {
	var getVolumeCmd string

	// Check for available volume commands
	if hasCommand("pamixer") {
		switch action {
		case "up":
			runCommand("pamixer --increase 5")
		case "down":
			runCommand("pamixer --decrease 5")
		case "mute":
			runCommand("pamixer --toggle-mute")
		}
		getVolumeCmd = "pamixer --get-volume"
	} else if hasCommand("pactl") {
		switch action {
		case "up":
			runCommand("pactl set-sink-volume @DEFAULT_SINK@ +5%")
		case "down":
			runCommand("pactl set-sink-volume @DEFAULT_SINK@ -5%")
		case "mute":
			runCommand("pactl set-sink-mute @DEFAULT_SINK@ toggle")
		}
		// For pactl, we'd need more complex parsing - simplified for now
		return
	} else {
		// Fallback to amixer
		switch action {
		case "up":
			runCommand("amixer set Master 5%+")
		case "down":
			runCommand("amixer set Master 5%-")
		case "mute":
			runCommand("amixer set Master toggle")
		}
		// For amixer, we'd need regex parsing - simplified for now
		return
	}

	// Get current volume and send update
	if volumeStr := runCommand(getVolumeCmd); volumeStr != "" {
		if volume, err := strconv.Atoi(volumeStr); err == nil {
			if volume == 0 {
				sendMessage("progress:volume:0:mute")
			} else {
				sendMessage(fmt.Sprintf("progress:volume:%d", volume))
			}
		}
	}
}

func handleBrightness(action string) {
	// Default brightness commands - these would be configurable
	var upCmd, downCmd, getCmd string

	if hasCommand("brightnessctl") {
		upCmd = "brightnessctl set +10%"
		downCmd = "brightnessctl set 10%-"
		getCmd = "brightnessctl get"
	} else if hasCommand("light") {
		upCmd = "light -A 10"
		downCmd = "light -U 10"
		getCmd = "light -G"
	} else {
		fmt.Fprintf(os.Stderr, "No brightness control command found\n")
		return
	}

	switch action {
	case "up":
		runCommand(upCmd)
	case "down":
		runCommand(downCmd)
	}

	// Get current brightness and send update
	if brightnessStr := runCommand(getCmd); brightnessStr != "" {
		if brightness, err := strconv.ParseFloat(brightnessStr, 64); err == nil {
			sendMessage(fmt.Sprintf("progress:brightness:%d", int(brightness)))
		}
	}
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "Usage: locus-client volume up|down|mute | brightness up|down | launcher [resume|fresh] [app] | <message>\n")
		os.Exit(1)
	}

	args := os.Args[1:]

	switch args[0] {
	case "volume":
		if len(args) < 2 {
			fmt.Fprintf(os.Stderr, "Usage: locus-client volume up|down|mute\n")
			os.Exit(1)
		}
		handleVolume(args[1])

	case "brightness":
		if len(args) < 2 {
			fmt.Fprintf(os.Stderr, "Usage: locus-client brightness up|down\n")
			os.Exit(1)
		}
		handleBrightness(args[1])

	case "launcher":
		if len(args) == 1 {
			// Just "launcher"
			sendMessage("launcher")
		} else {
			subcmd := args[1]
			if subcmd == "resume" || subcmd == "fresh" {
				if len(args) > 2 {
					// launcher resume/fresh with app name
					appName := strings.Join(args[2:], " ")
					sendMessage(fmt.Sprintf("launcher:%s %s", subcmd, appName))
				} else {
					// launcher resume/fresh without app name
					sendMessage(fmt.Sprintf("launcher:%s", subcmd))
				}
			} else if subcmd == "dmenu" {
				// Read options from stdin
				scanner := bufio.NewScanner(os.Stdin)
				var options strings.Builder
				for scanner.Scan() {
					options.WriteString(scanner.Text())
					options.WriteString("\n")
				}
				sendMessage(fmt.Sprintf("launcher dmenu:%s", options.String()))
			} else {
				// Regular launcher with app name
				appName := strings.Join(args[1:], " ")
				sendMessage(fmt.Sprintf("launcher %s", appName))
			}
		}

	default:
		// Send arbitrary message
		message := strings.Join(args, " ")
		if err := sendMessage(message); err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			os.Exit(1)
		}
	}
}
