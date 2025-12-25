package launcher

import (
	"strings"

	"github.com/sigma/locus-go/internal/config"
)

type ClipboardLauncher struct {
	config *config.Config
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

func (l *ClipboardLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	q := strings.TrimSpace(query)
	if q == "" {
		return []*LauncherItem{
			{
				Title:    "Clear Clipboard",
				Subtitle: "Clear all clipboard history",
				Icon:     "edit-clear-all",
				Command:  "wl-copy --clear",
			},
		}
	}

	items := []*LauncherItem{
		{
			Title:    "Show Clipboard History",
			Subtitle: "List and select from clipboard history",
			Icon:     "edit-paste",
			Command:  "cliphist list | head -50 | while read -r line; do echo \"$line\"; done | wl-copy -r 1",
		},
	}

	return items
}

func (l *ClipboardLauncher) HandlesEnter() bool {
	return true
}

func (l *ClipboardLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	return true
}

func (l *ClipboardLauncher) HandlesTab() bool {
	return false
}

func (l *ClipboardLauncher) HandleTab(query string) string {
	return query
}

func (l *ClipboardLauncher) Cleanup() {
}
