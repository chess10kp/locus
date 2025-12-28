package launcher

import (
	"fmt"
	"strings"

	"github.com/chess10kp/locus/internal/config"
)

type BrightnessLauncher struct {
	config  *config.Config
	upCmd   string
	downCmd string
}

type BrightnessLauncherFactory struct{}

func (f *BrightnessLauncherFactory) Name() string {
	return "brightness"
}

func (f *BrightnessLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewBrightnessLauncher(cfg)
}

func init() {
	RegisterLauncherFactory(&BrightnessLauncherFactory{})
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

func (l *BrightnessLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *BrightnessLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	items := []*LauncherItem{
		{
			Title:      "Brightness Up",
			Subtitle:   "Increase screen brightness by 5%",
			Icon:       "display-brightness-symbolic",
			ActionData: NewShellAction(l.upCmd),
			Launcher:   l,
		},
		{
			Title:      "Brightness Down",
			Subtitle:   "Decrease screen brightness by 5%",
			Icon:       "display-brightness-symbolic",
			ActionData: NewShellAction(l.downCmd),
			Launcher:   l,
		},
	}

	q := strings.TrimSpace(query)
	if q != "" {
		if strings.HasPrefix(q, "set ") {
			pct := strings.TrimPrefix(q, "set ")
			items = append(items, &LauncherItem{
				Title:      fmt.Sprintf("Set Brightness: %s%%", pct),
				Subtitle:   "Set brightness to specific percentage",
				Icon:       "display-brightness-symbolic",
				ActionData: NewShellAction(fmt.Sprintf("brightnessctl set %s%%", pct)),
				Launcher:   l,
			})
		} else if q == "up" || q == "down" {
			cmd := l.upCmd
			if q == "down" {
				cmd = l.downCmd
			}
			return []*LauncherItem{{
				Title:      fmt.Sprintf("Brightness %s", strings.Title(q)),
				Subtitle:   fmt.Sprintf("%s brightness by 5%%", strings.Title(q)),
				Icon:       "display-brightness-symbolic",
				ActionData: NewShellAction(cmd),
				Launcher:   l,
			}}
		}
	}

	return items
}

func (l *BrightnessLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *BrightnessLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *BrightnessLauncher) Cleanup() {
}

func (l *BrightnessLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}
