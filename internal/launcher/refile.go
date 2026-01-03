package launcher

import (
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"
	"time"

	"github.com/chess10kp/locus/internal/config"
)

type RefileLauncher struct {
	config    *config.Config
	wmCommand string
}

type RefileLauncherFactory struct{}

func (f *RefileLauncherFactory) Name() string {
	return "refile"
}

func (f *RefileLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewRefileLauncher(cfg)
}

func init() {
	RegisterLauncherFactory(&RefileLauncherFactory{})
}

func NewRefileLauncher(cfg *config.Config) *RefileLauncher {
	return &RefileLauncher{
		config:    cfg,
		wmCommand: detectWMCommand(),
	}
}

func (l *RefileLauncher) Name() string {
	return "refile"
}

func (l *RefileLauncher) CommandTriggers() []string {
	return []string{"refile", "rf"}
}

func (l *RefileLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *RefileLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *RefileLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	workspaces, err := l.fetchWorkspaces()
	if err != nil {
		fmt.Printf("Failed to fetch workspaces: %v\n", err)
		return []*LauncherItem{
			{
				Title:      "Failed to fetch workspaces",
				Subtitle:   err.Error(),
				Icon:       "dialog-error",
				ActionData: nil,
				Launcher:   l,
			},
		}
	}

	var currentWorkspace string
	var availableWorkspaces []Workspace

	for _, ws := range workspaces {
		if ws.Focused {
			currentWorkspace = ws.Name
		} else {
			availableWorkspaces = append(availableWorkspaces, ws)
		}
	}

	if currentWorkspace == "" {
		return []*LauncherItem{
			{
				Title:      "No focused workspace found",
				Subtitle:   "Cannot determine current workspace",
				Icon:       "dialog-warning",
				ActionData: nil,
				Launcher:   l,
			},
		}
	}

	queryLower := strings.ToLower(strings.TrimSpace(query))
	var items []*LauncherItem

	items = append(items, &LauncherItem{
		Title:      fmt.Sprintf("Refile from: %s", currentWorkspace),
		Subtitle:   "Choose workspace to swap with",
		Icon:       "exchange-places",
		ActionData: nil,
		Launcher:   l,
	})

	for _, ws := range availableWorkspaces {
		if queryLower != "" && !strings.Contains(strings.ToLower(ws.Name), queryLower) {
			continue
		}

		swapCommands := l.buildRefileCommands(currentWorkspace, ws.Name)

		items = append(items, &LauncherItem{
			Title:      fmt.Sprintf("Swap with: %s", ws.Name),
			Subtitle:   fmt.Sprintf("Move containers from %s to %s and vice versa", currentWorkspace, ws.Name),
			Icon:       "view-refresh",
			ActionData: NewShellAction(swapCommands),
			Launcher:   l,
			Metadata: map[string]string{
				"source_workspace": currentWorkspace,
				"target_workspace": ws.Name,
			},
		})
	}

	if len(items) == 1 {
		items = append(items, &LauncherItem{
			Title:      "No workspaces available",
			Subtitle:   "Create or switch to another workspace first",
			Icon:       "dialog-information",
			ActionData: nil,
			Launcher:   l,
		})
	}

	return items
}

func (l *RefileLauncher) buildRefileCommands(sourceWorkspace, targetWorkspace string) string {
	commands := []string{
		fmt.Sprintf("%s workspace tmp_swap_workspace", l.wmCommand),
		fmt.Sprintf("%s [workspace=\"%s\"] move container to workspace tmp_swap_workspace", l.wmCommand, sourceWorkspace),
		fmt.Sprintf("%s workspace %s", l.wmCommand, targetWorkspace),
		fmt.Sprintf("%s [workspace=\"%s\"] move container to workspace %s", l.wmCommand, targetWorkspace, sourceWorkspace),
		fmt.Sprintf("%s workspace tmp_swap_workspace", l.wmCommand),
		fmt.Sprintf("%s [workspace=\"tmp_swap_workspace\"] move container to workspace %s", l.wmCommand, targetWorkspace),
		fmt.Sprintf("%s workspace %s", l.wmCommand, sourceWorkspace),
	}

	return strings.Join(commands, " && ")
}

func (l *RefileLauncher) fetchWorkspaces() ([]Workspace, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	cmd := exec.CommandContext(ctx, l.wmCommand, "-t", "get_workspaces")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("failed to fetch workspaces: %w", err)
	}

	var wsList []Workspace
	if err := json.Unmarshal(output, &wsList); err != nil {
		return nil, fmt.Errorf("failed to parse workspaces: %w", err)
	}

	return wsList, nil
}

func (l *RefileLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *RefileLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *RefileLauncher) Cleanup() {
}

func (l *RefileLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}
