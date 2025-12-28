package launcher

import (
	"strings"

	"github.com/chess10kp/locus/internal/config"
)

type ClipboardLauncher struct {
	config *config.Config
}

type ClipboardLauncherFactory struct{}

func (f *ClipboardLauncherFactory) Name() string {
	return "clipboard"
}

func (f *ClipboardLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewClipboardLauncher(cfg)
}

func init() {
	RegisterLauncherFactory(&ClipboardLauncherFactory{})
}

func NewClipboardLauncher(cfg *config.Config) *ClipboardLauncher {
	return &ClipboardLauncher{
		config: cfg,
	}
}

func (l *ClipboardLauncher) Name() string {
	return "clipboard"
}

func (l *ClipboardLauncher) CommandTriggers() []string {
	return []string{"clipboard", "cb", "clip", "history"}
}

func (l *ClipboardLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *ClipboardLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *ClipboardLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	q := strings.TrimSpace(query)
	if q == "" {
		return []*LauncherItem{
			{
				Title:      "Clear Clipboard",
				Subtitle:   "Clear all clipboard history",
				Icon:       "edit-clear-all",
				ActionData: NewShellAction("wl-copy --clear"),
				Launcher:   l,
			},
		}
	}

	items := []*LauncherItem{
		{
			Title:      "Show Clipboard History",
			Subtitle:   "List and select from clipboard history",
			Icon:       "edit-paste",
			ActionData: NewShellAction("cliphist list | head -50 | while read -r line; do echo \"$line\"; done | wl-copy -r 1"),
			Launcher:   l,
		},
	}

	return items
}

func (l *ClipboardLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *ClipboardLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *ClipboardLauncher) Cleanup() {
}

func (l *ClipboardLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}
