package launcher

import (
	"strings"

	"github.com/chess10kp/locus/internal/config"
)

type WMFocusLauncher struct {
	config *config.Config
}

type WMFocusLauncherFactory struct{}

func (f *WMFocusLauncherFactory) Name() string {
	return "focus"
}

func (f *WMFocusLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewWMFocusLauncher(cfg)
}

func init() {
	RegisterLauncherFactory(&WMFocusLauncherFactory{})
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

func (l *WMFocusLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *WMFocusLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	items := []*LauncherItem{
		{
			Title:      "Focus Left",
			Subtitle:   "Focus window to the left",
			Icon:       "go-next-symbolic-rtl",
			ActionData: NewShellAction("swaymsg focus left"),
			Launcher:   l,
		},
		{
			Title:      "Focus Right",
			Subtitle:   "Focus window to the right",
			Icon:       "go-next-symbolic",
			ActionData: NewShellAction("swaymsg focus right"),
			Launcher:   l,
		},
		{
			Title:      "Focus Up",
			Subtitle:   "Focus window above",
			Icon:       "go-up-symbolic",
			ActionData: NewShellAction("swaymsg focus up"),
			Launcher:   l,
		},
		{
			Title:      "Focus Down",
			Subtitle:   "Focus window below",
			Icon:       "go-down-symbolic",
			ActionData: NewShellAction("swaymsg focus down"),
			Launcher:   l,
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

func (l *WMFocusLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *WMFocusLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *WMFocusLauncher) Cleanup() {
}

func (l *WMFocusLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}
