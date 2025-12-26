package launcher

import (
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
			Title:      "Take Screenshot (Screen)",
			Subtitle:   "Capture entire screen to clipboard",
			Icon:       "camera-photo-symbolic",
			ActionData: NewShellAction("grim - | wl-copy"),
		},
		{
			Title:      "Take Screenshot (Screen, Save)",
			Subtitle:   "Capture entire screen to file",
			Icon:       "camera-photo-symbolic",
			ActionData: NewShellAction("grim ~/Pictures/screenshot-$(date +%s).png"),
		},
		{
			Title:      "Take Screenshot (Region)",
			Subtitle:   "Select region to capture to clipboard",
			Icon:       "camera-photo-symbolic",
			ActionData: NewShellAction("slurp | grim -g - - | wl-copy"),
		},
		{
			Title:      "Take Screenshot (Region, Save)",
			Subtitle:   "Select region to capture to file",
			Icon:       "camera-photo-symbolic",
			ActionData: NewShellAction("slurp | grim -g - ~/Pictures/screenshot-$(date +%s).png"),
		},
		{
			Title:      "Take Screenshot (Window)",
			Subtitle:   "Capture focused window to clipboard",
			Icon:       "camera-photo-symbolic",
			ActionData: NewShellAction("swaymsg -t get_tree | jq -r '.. | select(.focused? and .pid?) | .rect | \"\\(.x),\\(.y) \\(.width)x\\(.height)\"' | grim -g - - | wl-copy"),
		},
	}

	q := query
	if q == "region" {
		return []*LauncherItem{{
			Title:      "Screenshot Region",
			Subtitle:   "Select region to capture",
			Icon:       "camera-photo-symbolic",
			ActionData: NewShellAction("slurp | grim -g - - | wl-copy"),
		}}
	}
	if q == "window" {
		return []*LauncherItem{{
			Title:      "Screenshot Window",
			Subtitle:   "Capture focused window",
			Icon:       "camera-photo-symbolic",
			ActionData: NewShellAction("swaymsg -t get_tree | jq -r '.. | select(.focused? and .pid?) | .rect | \"\\(.x),\\(.y) \\(.width)x\\(.height)\"' | grim -g - - | wl-copy"),
		}}
	}

	return items
}

func (l *ScreenshotLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *ScreenshotLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *ScreenshotLauncher) Cleanup() {
}

func (l *ScreenshotLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}
