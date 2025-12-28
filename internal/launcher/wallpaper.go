package launcher

import (
	"strings"

	"github.com/chess10kp/locus/internal/config"
)

type WallpaperLauncher struct {
	config *config.Config
}

type WallpaperLauncherFactory struct{}

func (f *WallpaperLauncherFactory) Name() string {
	return "wallpaper"
}

func (f *WallpaperLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewWallpaperLauncher(cfg)
}

func init() {
	RegisterLauncherFactory(&WallpaperLauncherFactory{})
}

func NewWallpaperLauncher(cfg *config.Config) *WallpaperLauncher {
	return &WallpaperLauncher{
		config: cfg,
	}
}

func (l *WallpaperLauncher) Name() string {
	return "wallpaper"
}

func (l *WallpaperLauncher) CommandTriggers() []string {
	return []string{"wallpaper", "wp", "bg"}
}

func (l *WallpaperLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *WallpaperLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	items := []*LauncherItem{
		{
			Title:      "Set Random Wallpaper",
			Subtitle:   "Pick random wallpaper from Pictures/wp/",
			Icon:       "preferences-desktop-wallpaper-symbolic",
			ActionData: NewShellAction("swww img $(find ~/Pictures/wp -type f | shuf -n 1)"),
		},
		{
			Title:      "Cycle Wallpaper",
			Subtitle:   "Switch to next wallpaper in sequence",
			Icon:       "preferences-desktop-wallpaper-symbolic",
			ActionData: NewShellAction("swww img $(find ~/Pictures/wp -type f | shuf -n 1)"),
		},
	}

	q := strings.TrimSpace(query)
	if q == "random" {
		return []*LauncherItem{{
			Title:      "Random Wallpaper",
			Subtitle:   "Set random wallpaper",
			Icon:       "preferences-desktop-wallpaper-symbolic",
			ActionData: NewShellAction("swww img $(find ~/Pictures/wp -type f | shuf -n 1)"),
		}}
	}

	return items
}

func (l *WallpaperLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *WallpaperLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *WallpaperLauncher) Cleanup() {
}

func (l *WallpaperLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}
