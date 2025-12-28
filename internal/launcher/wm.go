package launcher

import (
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"

	"github.com/chess10kp/locus/internal/config"
)

type Workspace struct {
	Number  int    `json:"num"`
	Name    string `json:"name"`
	Focused bool   `json:"focused"`
	Visible bool   `json:"visible"`
}

type SwayNode struct {
	ID               int64       `json:"id"`
	Name             string      `json:"name"`
	Type             string      `json:"type"`
	Window           *int64      `json:"window"`
	AppID            string      `json:"app_id"`
	WindowProperties WindowProps `json:"window_properties"`
	Nodes            []SwayNode  `json:"nodes"`
	FloatingNodes    []SwayNode  `json:"floating_nodes"`
}

type WindowProps struct {
	Class    string `json:"class"`
	Instance string `json:"instance"`
}

type WindowInfo struct {
	Name        string
	ConID       int64
	WindowID    int64
	Workspace   string
	AppID       string
	WindowClass string
}

type WMLauncher struct {
	config     *config.Config
	wmCommand  string
	workspaces []Workspace
	windows    []WindowInfo
}

type WMLauncherFactory struct{}

func (f *WMLauncherFactory) Name() string {
	return "wm"
}

func (f *WMLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewWMLauncher(cfg)
}

func init() {
	RegisterLauncherFactory(&WMLauncherFactory{})
}

func NewWMLauncher(cfg *config.Config) *WMLauncher {
	return &WMLauncher{
		config:    cfg,
		wmCommand: detectWMCommand(),
	}
}

func (l *WMLauncher) Name() string {
	return "wm"
}

func (l *WMLauncher) CommandTriggers() []string {
	return []string{"wm"}
}

func (l *WMLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *WMLauncher) GetGridConfig() *GridConfig {
	return nil
}

func detectWMCommand() string {
	commands := []string{"scrollmsg", "swaymsg", "i3-msg"}
	for _, cmd := range commands {
		if _, err := exec.LookPath(cmd); err == nil {
			return cmd
		}
	}
	return "swaymsg"
}

func (l *WMLauncher) fetchWorkspaces() ([]Workspace, error) {
	cmd := exec.Command(l.wmCommand, "-t", "get_workspaces")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}

	var wsList []Workspace
	if err := json.Unmarshal(output, &wsList); err != nil {
		return nil, err
	}

	return wsList, nil
}

func (l *WMLauncher) fetchWindows() ([]WindowInfo, error) {
	cmd := exec.Command(l.wmCommand, "-t", "get_tree")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}

	var tree SwayNode
	if err := json.Unmarshal(output, &tree); err != nil {
		return nil, err
	}

	windows := l.extractWindows(tree, "")
	l.windows = windows
	return windows, nil
}

func (l *WMLauncher) extractWindows(node SwayNode, workspace string) []WindowInfo {
	var windows []WindowInfo

	// Track workspace when we encounter one
	if node.Type == "workspace" {
		workspace = node.Name
	}

	// Collect windows (nodes that have a window field)
	if node.Window != nil && node.Type != "workspace" {
		windows = append(windows, WindowInfo{
			Name:        node.Name,
			ConID:       node.ID,
			WindowID:    *node.Window,
			Workspace:   workspace,
			AppID:       node.AppID,
			WindowClass: node.WindowProperties.Class,
		})
	}

	// Recursively search in nodes
	for _, child := range node.Nodes {
		windows = append(windows, l.extractWindows(child, workspace)...)
	}

	// Also search floating nodes
	for _, child := range node.FloatingNodes {
		windows = append(windows, l.extractWindows(child, workspace)...)
	}

	return windows
}

func (l *WMLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	var items []*LauncherItem

	queryLower := strings.ToLower(strings.TrimSpace(query))

	workspaces, err := l.fetchWorkspaces()
	if err != nil {
		fmt.Printf("Failed to fetch workspaces: %v\n", err)
		workspaces = []Workspace{}
	}

	windows, err := l.fetchWindows()
	if err != nil {
		fmt.Printf("Failed to fetch windows: %v\n", err)
	} else {
		windowItems := l.buildWindowItems(windows, queryLower)
		items = append(items, windowItems...)
	}

	wmItems := l.buildWindowManagementItems(queryLower)
	items = append(items, wmItems...)

	wsItems := l.buildWorkspaceItems(workspaces, queryLower)
	items = append(items, wsItems...)

	groupItems := l.buildWindowGroupItems(queryLower)
	items = append(items, groupItems...)

	scrollwmItems := l.buildScrollwmItems(queryLower)
	items = append(items, scrollwmItems...)

	utilityItems := l.buildUtilityItems(queryLower)
	items = append(items, utilityItems...)

	return items
}

func (l *WMLauncher) buildWindowManagementItems(query string) []*LauncherItem {
	commands := []struct {
		name      string
		subtitle  string
		icon      string
		cmdSuffix string
	}{
		{"Focus Left", "Focus window to the left", "go-next-symbolic-rtl", "focus left"},
		{"Focus Right", "Focus window to the right", "go-next-symbolic", "focus right"},
		{"Focus Up", "Focus window above", "go-up-symbolic", "focus up"},
		{"Focus Down", "Focus window below", "go-down-symbolic", "focus down"},
		{"Move Left", "Move window left", "go-previous-symbolic", "move left"},
		{"Move Right", "Move window right", "go-next", "move right"},
		{"Move Up", "Move window up", "go-up", "move up"},
		{"Move Down", "Move window down", "go-down", "move down"},
		{"Toggle Floating", "Toggle floating mode", "window-restore-symbolic", "floating toggle"},
		{"Toggle Fullscreen", "Toggle fullscreen mode", "view-fullscreen", "fullscreen toggle"},
		{"Split Horizontal", "Split container horizontally", "object-flip-horizontal", "split horizontal"},
		{"Split Vertical", "Split container vertically", "object-flip-vertical", "split vertical"},
		{"Layout Tabbed", "Set tabbed layout", "view-dual-symbolic", "layout tabbed"},
		{"Layout Stacking", "Set stacking layout", "view-list-symbolic", "layout stacking"},
	}

	var items []*LauncherItem
	for _, cmd := range commands {
		if query != "" && !strings.Contains(strings.ToLower(cmd.name), query) && !strings.Contains(strings.ToLower(cmd.subtitle), query) {
			continue
		}
		items = append(items, &LauncherItem{
			Title:      cmd.name,
			Subtitle:   cmd.subtitle,
			Icon:       cmd.icon,
			ActionData: NewShellAction(fmt.Sprintf("%s %s", l.wmCommand, cmd.cmdSuffix)),
			Launcher:   l,
		})
	}
	return items
}

func (l *WMLauncher) buildWorkspaceItems(workspaces []Workspace, query string) []*LauncherItem {
	var items []*LauncherItem

	utilityCommands := []struct {
		name      string
		subtitle  string
		icon      string
		cmdSuffix string
	}{
		{"Next Workspace", "Switch to next workspace", "go-next", "workspace next"},
		{"Previous Workspace", "Switch to previous workspace", "go-previous", "workspace prev"},
		{"Back and Forth", "Switch to previous workspace", "media-playlist-shuffle", "workspace back_and_forth"},
	}

	for _, cmd := range utilityCommands {
		if query != "" && !strings.Contains(strings.ToLower(cmd.name), query) && !strings.Contains(strings.ToLower(cmd.subtitle), query) {
			continue
		}
		items = append(items, &LauncherItem{
			Title:      cmd.name,
			Subtitle:   cmd.subtitle,
			Icon:       cmd.icon,
			ActionData: NewShellAction(fmt.Sprintf("%s %s", l.wmCommand, cmd.cmdSuffix)),
			Launcher:   l,
		})
	}

	for _, ws := range workspaces {
		title := fmt.Sprintf("Switch to: %s", ws.Name)
		if query != "" && !strings.Contains(strings.ToLower(title), query) {
			continue
		}
		items = append(items, &LauncherItem{
			Title:      title,
			Subtitle:   "Switch to workspace",
			Icon:       "workspace-switcher",
			ActionData: NewShellAction(fmt.Sprintf("%s workspace %s", l.wmCommand, ws.Name)),
			Launcher:   l,
			Metadata:   map[string]string{"workspace": ws.Name},
		})
	}

	return items
}

func (l *WMLauncher) buildWindowGroupItems(query string) []*LauncherItem {
	commands := []struct {
		name      string
		subtitle  string
		icon      string
		cmdSuffix string
	}{
		{"Move to Scratchpad", "Move window to scratchpad", "go-bottom", "move scratchpad"},
		{"Show Scratchpad", "Show scratchpad window", "go-top", "scratchpad show"},
		{"Toggle Sticky", "Toggle sticky mode", "pin", "sticky toggle"},
		{"Focus Parent", "Focus parent container", "go-up", "focus parent"},
	}

	var items []*LauncherItem
	for _, cmd := range commands {
		if query != "" && !strings.Contains(strings.ToLower(cmd.name), query) && !strings.Contains(strings.ToLower(cmd.subtitle), query) {
			continue
		}
		items = append(items, &LauncherItem{
			Title:      cmd.name,
			Subtitle:   cmd.subtitle,
			Icon:       cmd.icon,
			ActionData: NewShellAction(fmt.Sprintf("%s %s", l.wmCommand, cmd.cmdSuffix)),
			Launcher:   l,
		})
	}
	return items
}

func (l *WMLauncher) buildScrollwmItems(query string) []*LauncherItem {
	if l.wmCommand != "scrollmsg" {
		return []*LauncherItem{}
	}

	commands := []struct {
		name      string
		subtitle  string
		icon      string
		cmdSuffix string
	}{
		{"Toggle Overview", "Toggle overview mode", "view-grid-symbolic", "toggle overview"},
		{"Enable Animations", "Enable window animations", "media-playback-start", "enable animations"},
		{"Disable Animations", "Disable window animations", "media-playback-pause", "disable animations"},
		{"Reset Alignment", "Reset window alignment", "align-horizontal-center", "reset alignment"},
		{"Jump Mode", "Enter jump navigation mode", "format-text-underline", "jump mode"},
		{"Cycle Size", "Cycle window sizes", "zoom-in", "cycle size"},
		{"Set Size: Small", "Set window size to small", "zoom-out", "set size small"},
		{"Set Size: Medium", "Set window size to medium", "zoom-original", "set size medium"},
		{"Set Size: Large", "Set window size to large", "zoom-in", "set size large"},
		{"Fit Size", "Fit window to content", "fit-to-height", "fit size"},
	}

	var items []*LauncherItem
	for _, cmd := range commands {
		if query != "" && !strings.Contains(strings.ToLower(cmd.name), query) && !strings.Contains(strings.ToLower(cmd.subtitle), query) {
			continue
		}
		items = append(items, &LauncherItem{
			Title:      cmd.name,
			Subtitle:   cmd.subtitle,
			Icon:       cmd.icon,
			ActionData: NewShellAction(fmt.Sprintf("%s %s", l.wmCommand, cmd.cmdSuffix)),
			Launcher:   l,
		})
	}
	return items
}

func (l *WMLauncher) buildWindowItems(windows []WindowInfo, query string) []*LauncherItem {
	var items []*LauncherItem

	for _, win := range windows {
		// Filter by query
		if query != "" {
			lowerQuery := strings.ToLower(query)
			titleMatch := strings.Contains(strings.ToLower(win.Name), lowerQuery)
			appMatch := strings.Contains(strings.ToLower(win.WindowClass), lowerQuery)
			workspaceMatch := strings.Contains(strings.ToLower(win.Workspace), lowerQuery)

			if !titleMatch && !appMatch && !workspaceMatch {
				continue
			}
		}

		// Build subtitle with app class and workspace
		subtitle := win.WindowClass
		if subtitle == "" {
			subtitle = win.AppID
		}
		if subtitle != "" {
			subtitle += " · " + win.Workspace
		} else {
			subtitle = win.Workspace
		}

		// Determine icon based on app class
		icon := "window-new"
		if win.WindowClass != "" {
			icon = strings.ToLower(win.WindowClass)
		} else if win.AppID != "" {
			icon = strings.ToLower(win.AppID)
		}

		items = append(items, &LauncherItem{
			Title:      win.Name,
			Subtitle:   subtitle,
			Icon:       icon,
			ActionData: NewWindowFocusAction(win.ConID, win.Workspace),
			Launcher:   l,
			Metadata: map[string]string{
				"window_id": fmt.Sprintf("%d", win.WindowID),
				"con_id":    fmt.Sprintf("%d", win.ConID),
				"workspace": win.Workspace,
				"app_class": win.WindowClass,
			},
		})
	}

	return items
}

func (l *WMLauncher) buildUtilityItems(query string) []*LauncherItem {
	commands := []struct {
		name      string
		subtitle  string
		icon      string
		cmdSuffix string
	}{
		{"Kill Focused Window", "Close focused window", "window-close", "kill"},
		{"Kill All Windows", "Close all windows on workspace", "window-close-all", "[workspace focused] kill"},
		{"Reload Configuration", "Reload WM configuration", "document-reload", "reload"},
		{"Restart Window Manager", "Restart window manager", "system-reboot", "restart"},
		{"Exit Window Manager", "Exit window manager", "application-exit", "exit"},
	}

	var items []*LauncherItem
	for _, cmd := range commands {
		if query != "" && !strings.Contains(strings.ToLower(cmd.name), query) && !strings.Contains(strings.ToLower(cmd.subtitle), query) {
			continue
		}
		items = append(items, &LauncherItem{
			Title:      cmd.name,
			Subtitle:   cmd.subtitle,
			Icon:       cmd.icon,
			ActionData: NewShellAction(fmt.Sprintf("%s %s", l.wmCommand, cmd.cmdSuffix)),
			Launcher:   l,
		})
	}
	return items
}

func (l *WMLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return func(item *LauncherItem) error {
		workspaceName, ok := item.Metadata["workspace"]
		if !ok {
			return fmt.Errorf("item is not a workspace")
		}

		cmd := fmt.Sprintf("%s move container to workspace %s", l.wmCommand, workspaceName)
		shellCmd := exec.Command("sh", "-c", cmd)
		return shellCmd.Run()
	}, true
}

func (l *WMLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *WMLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *WMLauncher) Cleanup() {
}
