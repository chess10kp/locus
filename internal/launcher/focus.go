package launcher

import (
	"os/exec"
	"strings"
	"syscall"

	"github.com/sigma/locus-go/internal/config"
)

type WMFocusLauncher struct {
	config *config.Config
}

func NewWMFocusLauncher(cfg *config.Config) *WMFocusLauncher {
	return &WMFocusLauncher{
		config: cfg,
	}
}

func (l *WMFocusLauncher) Name() string {
	return "focus"
}

func (l *WMFocusLauncher) CommandTriggers() []string {
	return []string{"focus", "f"}
}

func (l *WMFocusLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *WMFocusLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	items := []*LauncherItem{
		{
			Title:    "Focus Left",
			Subtitle: "Focus window to the left",
			Icon:     "go-next-symbolic-rtl",
			Command:  "swaymsg focus left",
		},
		{
			Title:    "Focus Right",
			Subtitle: "Focus window to the right",
			Icon:     "go-next-symbolic",
			Command:  "swaymsg focus right",
		},
		{
			Title:    "Focus Up",
			Subtitle: "Focus window above",
			Icon:     "go-up-symbolic",
			Command:  "swaymsg focus up",
		},
		{
			Title:    "Focus Down",
			Subtitle: "Focus window below",
			Icon:     "go-down-symbolic",
			Command:  "swaymsg focus down",
		},
	}

	q := strings.ToLower(strings.TrimSpace(query))
	if q == "left" || q == "l" {
		return []*LauncherItem{items[0]}
	}
	if q == "right" || q == "r" {
		return []*LauncherItem{items[1]}
	}
	if q == "up" || q == "u" {
		return []*LauncherItem{items[2]}
	}
	if q == "down" || q == "d" {
		return []*LauncherItem{items[3]}
	}

	return items
}

func (l *WMFocusLauncher) HandlesEnter() bool {
	return true
}

func (l *WMFocusLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	cmd := exec.Command("swaymsg", "focus", query)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	return cmd.Start() == nil
}

func (l *WMFocusLauncher) HandlesTab() bool {
	return false
}

func (l *WMFocusLauncher) HandleTab(query string) string {
	return query
}

func (l *WMFocusLauncher) Cleanup() {
}
