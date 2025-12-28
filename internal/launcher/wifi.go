package launcher

import (
	"strings"

	"github.com/chess10kp/locus/internal/config"
)

type WifiLauncher struct {
	config *config.Config
}

type WifiLauncherFactory struct{}

func (f *WifiLauncherFactory) Name() string {
	return "wifi"
}

func (f *WifiLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewWifiLauncher(cfg)
}

func init() {
	RegisterLauncherFactory(&WifiLauncherFactory{})
}

func NewWifiLauncher(cfg *config.Config) *WifiLauncher {
	return &WifiLauncher{
		config: cfg,
	}
}

func (l *WifiLauncher) Name() string {
	return "wifi"
}

func (l *WifiLauncher) CommandTriggers() []string {
	return []string{"wifi", "wlan"}
}

func (l *WifiLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *WifiLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	q := strings.TrimSpace(query)

	if q == "" {
		return []*LauncherItem{
			{
				Title:      "WiFi Toggle",
				Subtitle:   "Enable/disable WiFi",
				Icon:       "network-wireless-symbolic",
				ActionData: NewShellAction("nmcli radio wifi on"),
			},
			{
				Title:      "WiFi Scan",
				Subtitle:   "Scan for networks",
				Icon:       "network-wireless-symbolic",
				ActionData: NewShellAction("nmcli device wifi scan"),
			},
			{
				Title:      "WiFi Status",
				Subtitle:   "Show current connection",
				Icon:       "network-wireless-symbolic",
				ActionData: NewShellAction("nmcli device wifi show"),
			},
		}
	}

	return []*LauncherItem{
		{
			Title:      "Toggle WiFi",
			Subtitle:   "Enable/disable WiFi",
			Icon:       "network-wireless-symbolic",
			ActionData: NewShellAction("nmcli radio wifi on"),
		},
		{
			Title:      "WiFi Status",
			Subtitle:   "Show current connection",
			Icon:       "network-wireless-symbolic",
			ActionData: NewShellAction("nmcli device wifi show"),
		},
	}
}

func (l *WifiLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *WifiLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *WifiLauncher) Cleanup() {
}

func (l *WifiLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}
