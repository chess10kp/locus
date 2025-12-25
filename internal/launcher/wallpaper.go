package launcher

import (
	"os/exec"
	"strings"
	"syscall"

	"github.com/sigma/locus-go/internal/config"
)

type WallpaperLauncher struct {
	config *config.Config
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
	return []*LauncherItem{
		{
			Title:    "Set Random Wallpaper",
			Subtitle: "Pick random wallpaper from Pictures/wp/",
			Icon:     "preferences-desktop-wallpaper-symbolic",
			Command:  "swww img $(find ~/Pictures/wp -type f | shuf -n 1)",
		},
		{
			Title:    "Cycle Wallpaper",
			Subtitle: "Switch to next wallpaper in sequence",
			Icon:     "preferences-desktop-wallpaper-symbolic",
			Command:  "swww img $(find ~/Pictures/wp -type f | shuf -n 1)",
		},
	}

	q := strings.TrimSpace(query)
	if q == "random" {
		return []*LauncherItem{{
			Title:    "Random Wallpaper",
			Subtitle: "Set random wallpaper",
			Icon:     "preferences-desktop-wallpaper-symbolic",
			Command:  "swww img $(find ~/Pictures/wp -type f | shuf -n 1)",
		}}
	}

	return []*LauncherItem{
		{
			Title:    "Set Random Wallpaper",
			Subtitle: "Pick random wallpaper from Pictures/wp/",
			Icon:     "preferences-desktop-wallpaper-symbolic",
			Command:  "swww img $(find ~/Pictures/wp -type f | shuf -n 1)",
		},
		{
			Title:    "Cycle Wallpaper",
			Subtitle: "Switch to next wallpaper in sequence",
			Icon:     "preferences-desktop-wallpaper-symbolic",
			Command:  "swww img $(find ~/Pictures/wp -type f | shuf -n 1)",
		},
	}
}

func (l *WallpaperLauncher) HandlesEnter() bool {
	return true
}

func (l *WallpaperLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	cmd := exec.Command("sh", "-c", "swww img $(find ~/Pictures/wp -type f | shuf -n 1)")
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	return cmd.Start() == nil
}

func (l *WallpaperLauncher) HandlesTab() bool {
	return false
}

func (l *WallpaperLauncher) HandleTab(query string) string {
	return query
}

func (l *WallpaperLauncher) Cleanup() {
}
