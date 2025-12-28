package launcher

import (
	"fmt"
	"strings"

	"github.com/chess10kp/locus/internal/config"
)

type ShellLauncher struct {
	config *config.Config
}

type ShellLauncherFactory struct{}

func (f *ShellLauncherFactory) Name() string {
	return "shell"
}

func (f *ShellLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewShellLauncher()
}

func init() {
	RegisterLauncherFactory(&ShellLauncherFactory{})
}

func NewShellLauncher() *ShellLauncher {
	return &ShellLauncher{}
}

func (l *ShellLauncher) Name() string {
	return "shell"
}

func (l *ShellLauncher) CommandTriggers() []string {
	return []string{">", "sh", "shell", "cmd", "command"}
}

func (l *ShellLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *ShellLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *ShellLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	if strings.TrimSpace(query) == "" {
		return []*LauncherItem{
			{
				Title:      "Type a shell command to execute",
				Subtitle:   "Example: ls -la, cd /home, or any command",
				Icon:       "utilities-terminal",
				ActionData: NewShellAction(""),
				Launcher:   l,
			},
		}
	}

	return []*LauncherItem{
		{
			Title:      fmt.Sprintf("Run: %s", query),
			Subtitle:   "Execute in shell",
			Icon:       "utilities-terminal",
			ActionData: NewShellAction(query),
			Launcher:   l,
		},
	}
}

func (l *ShellLauncher) GetHooks() []Hook {
	return []Hook{} // Shell launcher doesn't need custom hooks
}

func (l *ShellLauncher) Rebuild(ctx *LauncherContext) error {
	// Shell launcher doesn't need to rebuild
	return nil
}

func (l *ShellLauncher) Cleanup() {
}

func (l *ShellLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}

type WebLauncher struct {
	config *config.Config
}

type WebLauncherFactory struct{}

func (f *WebLauncherFactory) Name() string {
	return "web"
}

func (f *WebLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewWebLauncher()
}

func init() {
	RegisterLauncherFactory(&WebLauncherFactory{})
}

func NewWebLauncher() *WebLauncher {
	return &WebLauncher{}
}

func (l *WebLauncher) Name() string {
	return "web"
}

func (l *WebLauncher) CommandTriggers() []string {
	return []string{":", "web", "url", "open"}
}

func (l *WebLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *WebLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *WebLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	if strings.TrimSpace(query) == "" {
		return []*LauncherItem{
			{
				Title:      "Type a URL or search query",
				Subtitle:   "Example: google.com, https://example.com, or search terms",
				Icon:       "web-browser",
				ActionData: NewShellAction(""),
				Launcher:   l,
			},
		}
	}

	url := query
	if !strings.HasPrefix(strings.ToLower(query), "http://") &&
		!strings.HasPrefix(strings.ToLower(query), "https://") {
		url = "https://" + query
	}

	return []*LauncherItem{
		{
			Title:      fmt.Sprintf("Open: %s", query),
			Subtitle:   url,
			Icon:       "web-browser",
			ActionData: NewShellAction(fmt.Sprintf("xdg-open %s", url)),
			Launcher:   l,
		},
	}
}

func (l *WebLauncher) GetHooks() []Hook {
	return []Hook{} // Web launcher doesn't need custom hooks
}

func (l *WebLauncher) Rebuild(ctx *LauncherContext) error {
	// Web launcher doesn't need to rebuild
	return nil
}

func (l *WebLauncher) Cleanup() {
}

func (l *WebLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}

type CalcLauncher struct {
	config *config.Config
}

type CalcLauncherFactory struct{}

func (f *CalcLauncherFactory) Name() string {
	return "calc"
}

func (f *CalcLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewCalcLauncher()
}

func init() {
	RegisterLauncherFactory(&CalcLauncherFactory{})
}

func NewCalcLauncher() *CalcLauncher {
	return &CalcLauncher{}
}

func (l *CalcLauncher) Name() string {
	return "calc"
}

func (l *CalcLauncher) CommandTriggers() []string {
	return []string{"=", "calc", "math"}
}

func (l *CalcLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *CalcLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *CalcLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	if strings.TrimSpace(query) == "" {
		return []*LauncherItem{
			{
				Title:      "Type a mathematical expression",
				Subtitle:   "Example: 2+2, sin(3.14), or sqrt(16)",
				Icon:       "accessories-calculator",
				ActionData: NewShellAction(""),
				Launcher:   l,
			},
		}
	}

	return []*LauncherItem{
		{
			Title:      fmt.Sprintf("Calculate: %s", query),
			Subtitle:   "Evaluate expression",
			Icon:       "accessories-calculator",
			ActionData: NewShellAction(fmt.Sprintf("qalc %s", query)),
			Launcher:   l,
		},
	}
}

func (l *CalcLauncher) GetHooks() []Hook {
	return []Hook{} // Calc launcher doesn't need custom hooks
}

func (l *CalcLauncher) Rebuild(ctx *LauncherContext) error {
	// Calc launcher doesn't need to rebuild
	return nil
}

func (l *CalcLauncher) Cleanup() {
}

func (l *CalcLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}

type HelpLauncher struct {
	config *config.Config
}

type HelpLauncherFactory struct{}

func (f *HelpLauncherFactory) Name() string {
	return "help"
}

func (f *HelpLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewHelpLauncher()
}

func init() {
	RegisterLauncherFactory(&HelpLauncherFactory{})
}

func NewHelpLauncher() *HelpLauncher {
	return &HelpLauncher{}
}

func (l *HelpLauncher) Name() string {
	return "help"
}

func (l *HelpLauncher) CommandTriggers() []string {
	return []string{"?"}
}

func (l *HelpLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *HelpLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *HelpLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	if ctx.Registry == nil {
		return []*LauncherItem{
			{
				Title:    "Registry not available",
				Subtitle: "Cannot load launcher information",
				Icon:     "dialog-error",
				Launcher: l,
			},
		}
	}

	launchers := ctx.Registry.GetAllLaunchers()
	items := make([]*LauncherItem, 0, len(launchers))

	query = strings.ToLower(strings.TrimSpace(query))

	for _, launcher := range launchers {
		name := launcher.Name()
		triggers := launcher.CommandTriggers()

		triggerStr := ""
		if len(triggers) > 0 {
			triggerStr = strings.Join(triggers, ", ")
		}

		title := fmt.Sprintf("%s", name)
		subtitle := fmt.Sprintf("Prefixes: %s", triggerStr)

		if triggerStr == "" {
			subtitle = "Default launcher (no prefix needed)"
		}

		if query != "" {
			if !strings.Contains(strings.ToLower(title), query) && !strings.Contains(strings.ToLower(subtitle), query) {
				continue
			}
		}

		var icon string
		switch name {
		case "apps":
			icon = "applications-other"
		case "shell":
			icon = "utilities-terminal"
		case "web":
			icon = "web-browser"
		case "calc":
			icon = "accessories-calculator"
		case "timer":
			icon = "clock"
		case "help":
			icon = "help-about"
		case "wifi":
			icon = "network-wireless"
		case "music":
			icon = "audio-x-generic"
		case "wallpaper":
			icon = "preferences-desktop-wallpaper"
		case "file":
			icon = "folder"
		case "screenshot":
			icon = "camera-photo"
		case "lock":
			icon = "system-lock-screen"
		case "focus":
			icon = "view-restore"
		case "kill":
			icon = "window-close"
		case "brightness":
			icon = "display-brightness"
		case "clipboard":
			icon = "edit-paste"
		default:
			icon = "application-x-executable"
		}

		items = append(items, &LauncherItem{
			Title:    title,
			Subtitle: subtitle,
			Icon:     icon,
			Launcher: launcher,
		})
	}

	if len(items) == 0 {
		return []*LauncherItem{
			{
				Title:    "No launchers found",
				Subtitle: "Try a different search term",
				Icon:     "dialog-information",
				Launcher: l,
			},
		}
	}

	return items
}

func (l *HelpLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *HelpLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *HelpLauncher) Cleanup() {
}

func (l *HelpLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}
