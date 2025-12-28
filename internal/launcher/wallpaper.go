package launcher

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"syscall"
	"time"

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
	return LauncherSizeModeGrid
}

func (l *WallpaperLauncher) GetGridConfig() *GridConfig {
	return &GridConfig{
		Columns:          5,
		ItemWidth:        200,
		ItemHeight:       150,
		Spacing:          10,
		ShowMetadata:     false,
		MetadataPosition: MetadataPositionHidden,
		AspectRatio:      AspectRatioOriginal,
	}
}

func (l *WallpaperLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	q := strings.TrimSpace(query)

	// Special commands
	if q == "random" {
		return []*LauncherItem{{
			Title:      "Random Wallpaper",
			Subtitle:   "Set random wallpaper",
			Icon:       "preferences-desktop-wallpaper-symbolic",
			ActionData: NewShellAction("swww img $(find ~/Pictures/wp -type f | shuf -n 1)"),
			Launcher:   l,
		}}
	}

	// List wallpapers in grid mode by default
	homeDir, _ := os.UserHomeDir()
	wallpaperDir := filepath.Join(homeDir, "Pictures", "wp")

	// If query is empty, list all wallpapers
	if q == "" {
		return l.listWallpapers(wallpaperDir)
	}

	// Try to match wallpaper files by name
	wallpapers := l.listWallpapers(wallpaperDir)
	var matched []*LauncherItem
	for _, wp := range wallpapers {
		if strings.Contains(strings.ToLower(wp.Title), strings.ToLower(q)) {
			matched = append(matched, wp)
		}
	}

	if len(matched) > 0 {
		return matched
	}

	// Fallback to list view for other commands
	return []*LauncherItem{
		{
			Title:      "Set Random Wallpaper",
			Subtitle:   "Pick random wallpaper from Pictures/wp/",
			Icon:       "preferences-desktop-wallpaper-symbolic",
			ActionData: NewShellAction("swww img $(find ~/Pictures/wp -type f | shuf -n 1)"),
			Launcher:   l,
		},
		{
			Title:      "Cycle Wallpaper",
			Subtitle:   "Switch to next wallpaper in sequence",
			Icon:       "preferences-desktop-wallpaper-symbolic",
			ActionData: NewShellAction("swww img $(find ~/Pictures/wp -type f | shuf -n 1)"),
			Launcher:   l,
		},
	}
}

func (l *WallpaperLauncher) listWallpapers(dir string) []*LauncherItem {
	items := []*LauncherItem{}

	// Execute find command with timeout to prevent hanging
	cmdCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	cmd := exec.CommandContext(cmdCtx, "find", dir, "-type", "f", "-name", "*.jpg", "-o", "-name", "*.jpeg", "-o", "-name", "*.png", "-o", "-name", "*.webp")
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	output, err := cmd.CombinedOutput()

	if cmdCtx.Err() == context.DeadlineExceeded {
		return items
	}

	if err != nil {
		return items
	}

	// Parse wallpaper files
	lines := strings.Split(string(output), "\n")
	// Sort by modification time (newest first)
	type wallpaperInfo struct {
		path  string
		name  string
		mtime time.Time
	}
	var wallpapers []wallpaperInfo

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		// Get file info for sorting
		info, err := os.Stat(line)
		if err != nil {
			continue
		}

		filename := filepath.Base(line)
		wallpapers = append(wallpapers, wallpaperInfo{
			path:  line,
			name:  filename,
			mtime: info.ModTime(),
		})
	}

	// Sort by modification time (newest first)
	sort.Slice(wallpapers, func(i, j int) bool {
		return wallpapers[i].mtime.After(wallpapers[j].mtime)
	})

	// Limit to 25 wallpapers
	maxWallpapers := 25
	if len(wallpapers) > maxWallpapers {
		wallpapers = wallpapers[:maxWallpapers]
	}

	// Create launcher items
	for i, wp := range wallpapers {
		items = append(items, &LauncherItem{
			Title:      wp.name,
			Subtitle:   fmt.Sprintf("Set as wallpaper"),
			Icon:       "image-x-generic",
			ActionData: NewShellAction(fmt.Sprintf("swww img %s", wp.path)),
			Launcher:   l,
			IsGridItem: true,
			ImagePath:  wp.path,
		})

		// Limit to first 25 items
		if i >= maxWallpapers-1 {
			break
		}
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
