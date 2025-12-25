package launcher

import (
	"fmt"
	"os/exec"
	"strings"
	"syscall"

	"github.com/sigma/locus-go/internal/config"
)

type BrightnessLauncher struct {
	config  *config.Config
	upCmd   string
	downCmd string
}

func NewBrightnessLauncher(cfg *config.Config) *BrightnessLauncher {
	return &BrightnessLauncher{
		config:  cfg,
		upCmd:   "brightnessctl set +5%",
		downCmd: "brightnessctl set 5%-",
	}
}

func (l *BrightnessLauncher) Name() string {
	return "brightness"
}

func (l *BrightnessLauncher) CommandTriggers() []string {
	return []string{"brightness", "bright", "bri"}
}

func (l *BrightnessLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *BrightnessLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	items := []*LauncherItem{
		{
			Title:    "Brightness Up",
			Subtitle: "Increase screen brightness by 5%",
			Icon:     "display-brightness-symbolic",
			Command:  l.upCmd,
		},
		{
			Title:    "Brightness Down",
			Subtitle: "Decrease screen brightness by 5%",
			Icon:     "display-brightness-symbolic",
			Command:  l.downCmd,
		},
	}

	q := strings.TrimSpace(query)
	if q != "" {
		if strings.HasPrefix(q, "set ") {
			pct := strings.TrimPrefix(q, "set ")
			items = append(items, &LauncherItem{
				Title:    fmt.Sprintf("Set Brightness: %s%%", pct),
				Subtitle: "Set brightness to specific percentage",
				Icon:     "display-brightness-symbolic",
				Command:  fmt.Sprintf("brightnessctl set %s%%", pct),
			})
		} else if q == "up" || q == "down" {
			cmd := l.upCmd
			if q == "down" {
				cmd = l.downCmd
			}
			return []*LauncherItem{{
				Title:    fmt.Sprintf("Brightness %s", strings.Title(q)),
				Subtitle: fmt.Sprintf("%s brightness by 5%%", strings.Title(q)),
				Icon:     "display-brightness-symbolic",
				Command:  cmd,
			}}
		}
	}

	return items
}

func (l *BrightnessLauncher) HandlesEnter() bool {
	return true
}

func (l *BrightnessLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	q := strings.TrimSpace(query)
	if q == "" || q == "up" {
		cmd := exec.Command("sh", "-c", l.upCmd)
		cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
		return cmd.Start() == nil
	}
	if q == "down" {
		cmd := exec.Command("sh", "-c", l.downCmd)
		cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
		return cmd.Start() == nil
	}
	if strings.HasPrefix(q, "set ") {
		pct := strings.TrimPrefix(q, "set ")
		cmd := exec.Command("brightnessctl", "set", pct+"%")
		cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
		return cmd.Start() == nil
	}
	return false
}

func (l *BrightnessLauncher) HandlesTab() bool {
	return false
}

func (l *BrightnessLauncher) HandleTab(query string) string {
	return query
}

func (l *BrightnessLauncher) Cleanup() {
}
