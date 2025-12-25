package launcher

import (
	"os/exec"
	"syscall"

	"github.com/sigma/locus-go/internal/config"
)

type ScreenshotLauncher struct {
	config *config.Config
}

func NewScreenshotLauncher(cfg *config.Config) *ScreenshotLauncher {
	return &ScreenshotLauncher{
		config: cfg,
	}
}

func (l *ScreenshotLauncher) Name() string {
	return "screenshot"
}

func (l *ScreenshotLauncher) CommandTriggers() []string {
	return []string{"screenshot", "shot", "scr", "ss"}
}

func (l *ScreenshotLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *ScreenshotLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	items := []*LauncherItem{
		{
			Title:    "Take Screenshot (Screen)",
			Subtitle: "Capture entire screen to clipboard",
			Icon:     "camera-photo-symbolic",
			Command:  "grim - | wl-copy",
		},
		{
			Title:    "Take Screenshot (Screen, Save)",
			Subtitle: "Capture entire screen to file",
			Icon:     "camera-photo-symbolic",
			Command:  "grim ~/Pictures/screenshot-$(date +%s).png",
		},
		{
			Title:    "Take Screenshot (Region)",
			Subtitle: "Select region to capture to clipboard",
			Icon:     "camera-photo-symbolic",
			Command:  "slurp | grim -g - - | wl-copy",
		},
		{
			Title:    "Take Screenshot (Region, Save)",
			Subtitle: "Select region to capture to file",
			Icon:     "camera-photo-symbolic",
			Command:  "slurp | grim -g - ~/Pictures/screenshot-$(date +%s).png",
		},
		{
			Title:    "Take Screenshot (Window)",
			Subtitle: "Capture focused window to clipboard",
			Icon:     "camera-photo-symbolic",
			Command:  "swaymsg -t get_tree | jq -r '.. | select(.focused? and .pid?) | .rect | \"\\(.x),\\(.y) \\(.width)x\\(.height)\"' | grim -g - - | wl-copy",
		},
	}

	q := query
	if q == "region" {
		return []*LauncherItem{{
			Title:    "Screenshot Region",
			Subtitle: "Select region to capture",
			Icon:     "camera-photo-symbolic",
			Command:  "slurp | grim -g - - | wl-copy",
		}}
	}
	if q == "window" {
		return []*LauncherItem{{
			Title:    "Screenshot Window",
			Subtitle: "Capture focused window",
			Icon:     "camera-photo-symbolic",
			Command:  "swaymsg -t get_tree | jq -r '.. | select(.focused? and .pid?) | .rect | \"\\(.x),\\(.y) \\(.width)x\\(.height)\"' | grim -g - - | wl-copy",
		}}
	}

	return items
}

func (l *ScreenshotLauncher) HandlesEnter() bool {
	return true
}

func (l *ScreenshotLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	cmd := exec.Command("sh", "-c", "grim - | wl-copy")
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	return cmd.Start() == nil
}

func (l *ScreenshotLauncher) HandlesTab() bool {
	return false
}

func (l *ScreenshotLauncher) HandleTab(query string) string {
	return query
}

func (l *ScreenshotLauncher) Cleanup() {
}
