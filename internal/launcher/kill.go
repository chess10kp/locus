package launcher

import (
	"context"
	"os/exec"
	"strings"
	"time"

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

func (l *KillLauncher) Populate(query string, launcherCtx *LauncherContext) []*LauncherItem {
	q := strings.TrimSpace(query)
	if q == "" {
		return []*LauncherItem{
			{
				Title:      "Kill Window",
				Subtitle:   "Close focused window",
				Icon:       "window-close-symbolic",
				ActionData: NewShellAction("swaymsg kill"),
			},
			{
				Title:      "Kill All Windows",
				Subtitle:   "Close all windows on current workspace",
				Icon:       "window-close-symbolic",
				ActionData: NewShellAction("swaymsg '[workspace focused] kill'"),
			},
		}
	}

	// Don't run expensive command for short queries
	if len(q) < 2 {
		return []*LauncherItem{
			{
				Title:      "Kill Window",
				Subtitle:   "Close focused window",
				Icon:       "window-close-symbolic",
				ActionData: NewShellAction("swaymsg kill"),
			},
		}
	}

	// Execute swaymsg command with timeout to prevent hanging
	cmdCtx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
	defer cancel()

	cmd := exec.CommandContext(cmdCtx, "sh", "-c", "swaymsg -t get_tree | jq -r '.. | select(.focused? and .pid?) | .name'")
	output, err := cmd.Output()

	focusedWindow := "unknown"
	if err == nil {
		focusedWindow = strings.TrimSpace(string(output))
	}

	items := []*LauncherItem{
		{
			Title:      "Kill Focused: " + focusedWindow,
			Subtitle:   "Close focused window",
			Icon:       "window-close-symbolic",
			ActionData: NewShellAction("swaymsg kill"),
		},
	}

	if strings.HasPrefix(q, "by-name ") {
		name := strings.TrimPrefix(q, "by-name ")
		items = append(items, &LauncherItem{
			Title:      "Kill by name: " + name,
			Subtitle:   "Kill all windows matching name",
			Icon:       "window-close-symbolic",
			ActionData: NewShellAction("swaymsg '[title=\"" + name + "\"] kill'"),
		})
	}

	if strings.HasPrefix(q, "all") {
		items = append(items, &LauncherItem{
			Title:      "Kill All Windows",
			Subtitle:   "Close all windows on current workspace",
			Icon:       "window-close-symbolic",
			ActionData: NewShellAction("swaymsg '[workspace focused] kill'"),
		})
	}

	return items
}

func (l *KillLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *KillLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *KillLauncher) Cleanup() {
}

func (l *KillLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}
