package launcher

import (
	"os/exec"
	"strings"
	"syscall"

	"github.com/sigma/locus-go/internal/config"
)

type WifiLauncher struct {
	config *config.Config
}

func NewWifiLauncher(cfg *config.Config) *WifiLauncher {
	return &WifiLauncher{
		config: cfg,
	}
}

func (l *WifiLauncher) Name() string {
	return "wifi"
}

func (l *WifiLauncher) CommandTriggers() []string {
	return []string{"wifi", "wlan"}
}

func (l *WifiLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *WifiLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	q := strings.TrimSpace(query)

	if q == "" {
		return []*LauncherItem{
			{
				Title:    "WiFi Toggle",
				Subtitle: "Enable/disable WiFi",
				Icon:     "network-wireless-symbolic",
				Command:  "nmcli radio wifi on",
			},
			{
				Title:    "WiFi Scan",
				Subtitle: "Scan for networks",
				Icon:     "network-wireless-symbolic",
				Command:  "nmcli device wifi scan",
			},
			{
				Title:    "WiFi Status",
				Subtitle: "Show current connection",
				Icon:     "network-wireless-symbolic",
				Command:  "nmcli device wifi show",
			},
		}
	}

	return []*LauncherItem{
		{
			Title:    "Toggle WiFi",
			Subtitle: "Enable/disable WiFi",
			Icon:     "network-wireless-symbolic",
			Command:  "nmcli radio wifi on",
		},
		{
			Title:    "WiFi Status",
			Subtitle: "Show current connection",
			Icon:     "network-wireless-symbolic",
			Command:  "nmcli device wifi show",
		},
	}
}

func (l *WifiLauncher) HandlesEnter() bool {
	return true
}

func (l *WifiLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	q := strings.TrimSpace(query)

	if q == "" || q == "toggle" || q == "on" {
		cmd := exec.Command("nmcli", "radio", "wifi", "on")
		cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
		return cmd.Start() == nil
	}

	if q == "off" {
		cmd := exec.Command("nmcli", "radio", "wifi", "off")
		cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
		return cmd.Start() == nil
	}

	if q == "scan" {
		cmd := exec.Command("nmcli", "device", "wifi", "scan")
		cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
		return cmd.Start() == nil
	}

	return false
}

func (l *WifiLauncher) HandlesTab() bool {
	return false
}

func (l *WifiLauncher) HandleTab(query string) string {
	return query
}

func (l *WifiLauncher) Cleanup() {
}
