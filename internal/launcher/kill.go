package launcher

import (
	"os/exec"
	"strings"
	"syscall"

	"github.com/sigma/locus-go/internal/config"
)

type KillLauncher struct {
	config *config.Config
}

func NewKillLauncher(cfg *config.Config) *KillLauncher {
	return &KillLauncher{
		config: cfg,
	}
}

func (l *KillLauncher) Name() string {
	return "kill"
}

func (l *KillLauncher) CommandTriggers() []string {
	return []string{"kill", "k"}
}

func (l *KillLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *KillLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	q := strings.TrimSpace(query)
	if q == "" {
		return []*LauncherItem{
			{
				Title:    "Kill Window",
				Subtitle: "Close focused window",
				Icon:     "window-close-symbolic",
				Command:  "swaymsg kill",
			},
			{
				Title:    "Kill All Windows",
				Subtitle: "Close all windows on current workspace",
				Icon:     "window-close-symbolic",
				Command:  "swaymsg '[workspace focused] kill'",
			},
		}
	}

	cmd := exec.Command("sh", "-c", "swaymsg -t get_tree | jq -r '.. | select(.focused? and .pid?) | .name'")
	output, _ := cmd.Output()
	focusedWindow := strings.TrimSpace(string(output))

	items := []*LauncherItem{
		{
			Title:    "Kill Focused: " + focusedWindow,
			Subtitle: "Close focused window",
			Icon:     "window-close-symbolic",
			Command:  "swaymsg kill",
		},
	}

	if strings.HasPrefix(q, "by-name ") {
		name := strings.TrimPrefix(q, "by-name ")
		items = append(items, &LauncherItem{
			Title:    "Kill by name: " + name,
			Subtitle: "Kill all windows matching name",
			Icon:     "window-close-symbolic",
			Command:  "swaymsg '[title=\"" + name + "\"] kill'",
		})
	}

	if strings.HasPrefix(q, "all") {
		items = append(items, &LauncherItem{
			Title:    "Kill All Windows",
			Subtitle: "Close all windows on current workspace",
			Icon:     "window-close-symbolic",
			Command:  "swaymsg '[workspace focused] kill'",
		})
	}

	return items
}

func (l *KillLauncher) HandlesEnter() bool {
	return true
}

func (l *KillLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	cmd := exec.Command("sh", "-c", "swaymsg kill")
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	return cmd.Start() == nil
}

func (l *KillLauncher) HandlesTab() bool {
	return false
}

func (l *KillLauncher) HandleTab(query string) string {
	return query
}

func (l *KillLauncher) Cleanup() {
}
