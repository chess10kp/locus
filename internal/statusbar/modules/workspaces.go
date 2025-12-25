package modules

import (
	"context"
	"encoding/json"
	"log"
	"os"
	"os/exec"
	"strings"

	"github.com/gotk3/gotk3/gtk"
	"github.com/joshuarubin/go-sway"
	"github.com/sigma/locus-go/internal/statusbar"
)

// Workspace represents a sway workspace
type Workspace struct {
	Name    string `json:"name"`
	Focused bool   `json:"focused"`
	Visible bool   `json:"visible"`
	Num     int64  `json:"num"`
	Output  string `json:"output"`
}

// getWorkspacesFromSway gets workspaces from sway IPC
func getWorkspacesFromSway() ([]Workspace, error) {
	// Try using go-sway library first
	ctx := context.Background()
	client, err := sway.New(ctx)
	if err == nil {
		swayWorkspaces, err := client.GetWorkspaces(ctx)
		if err == nil {
			workspaces := make([]Workspace, len(swayWorkspaces))
			for i, ws := range swayWorkspaces {
				workspaces[i] = Workspace{
					Name:    ws.Name,
					Focused: ws.Focused,
					Visible: ws.Visible,
					Num:     ws.Num,
					Output:  ws.Output,
				}
			}
			return workspaces, nil
		}
	}

	// Fallback to swaymsg command
	env := os.Environ()
	// Remove LD_PRELOAD to avoid child process issues
	for i, e := range env {
		if strings.HasPrefix(e, "LD_PRELOAD=") {
			env = append(env[:i], env[i+1:]...)
			break
		}
	}

	cmd := exec.Command("swaymsg", "-t", "get_workspaces")
	cmd.Env = env
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}

	var workspaces []Workspace
	if err := json.Unmarshal(output, &workspaces); err != nil {
		return nil, err
	}

	return workspaces, nil
}

// WorkspacesModule displays workspace indicators
type WorkspacesModule struct {
	*statusbar.BaseModule
	widget       *gtk.Label
	workspaces   []string
	focusedIndex int
}

// NewWorkspacesModule creates a new workspaces module
func NewWorkspacesModule() *WorkspacesModule {
	return &WorkspacesModule{
		BaseModule:   statusbar.NewBaseModule("workspaces", statusbar.UpdateModePeriodic),
		widget:       nil,
		workspaces:   []string{"1", "2", "3", "4", "5"},
		focusedIndex: 0,
	}
}

// CreateWidget creates a workspaces label widget
func (m *WorkspacesModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.formatWorkspaces())
	if err != nil {
		return nil, err
	}

	m.widget = label

	helper := &statusbar.WidgetHelper{}
	if err := helper.ApplyStylesToWidget(label, m.GetStyles(), m.GetCSSClasses()); err != nil {
		return nil, err
	}

	return label, nil
}

// UpdateWidget updates workspaces widget
func (m *WorkspacesModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	// Poll workspaces from sway
	workspaces, err := getWorkspacesFromSway()
	if err != nil {
		log.Printf("Failed to get workspaces from sway: %v", err)
		// Keep existing workspaces if polling fails
	} else {
		// Update workspaces list
		m.workspaces = make([]string, len(workspaces))
		for i, ws := range workspaces {
			m.workspaces[i] = ws.Name
			if ws.Focused {
				m.focusedIndex = int(ws.Num) - 1 // Assuming workspaces start from 1
			}
		}
	}

	formatted := m.formatWorkspaces()
	label.SetText(formatted)

	return nil
}

// Initialize initializes the module with configuration
func (m *WorkspacesModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if showLabels, ok := config["show_labels"].(bool); ok && !showLabels {
		m.widget.SetName("workspaces-icons")
	}

	m.SetCSSClasses([]string{"workspaces-module"})

	return nil
}

// formatWorkspaces formats workspaces for display
func (m *WorkspacesModule) formatWorkspaces() string {
	var builder strings.Builder

	for i, ws := range m.workspaces {
		if i > 0 {
			builder.WriteString(" ")
		}

		if i == m.focusedIndex {
			builder.WriteString("[")
			builder.WriteString(ws)
			builder.WriteString("]")
		} else {
			builder.WriteString(ws)
		}
	}

	return builder.String()
}

// SetWorkspaces sets the workspaces list
func (m *WorkspacesModule) SetWorkspaces(workspaces []string) {
	m.workspaces = workspaces
}

// SetFocusedIndex sets the focused workspace index
func (m *WorkspacesModule) SetFocusedIndex(index int) {
	if index >= 0 && index < len(m.workspaces) {
		m.focusedIndex = index
	}
}

// WorkspacesModuleFactory is a factory for creating WorkspacesModule instances
type WorkspacesModuleFactory struct{}

// CreateModule creates a new WorkspacesModule instance
func (f *WorkspacesModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewWorkspacesModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns the module name
func (f *WorkspacesModuleFactory) ModuleName() string {
	return "workspaces"
}

// DefaultConfig returns the default configuration
func (f *WorkspacesModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"show_labels": true,
		"interval":    "1s",
		"css_classes": []string{"workspaces-module"},
	}
}

// Dependencies returns the module dependencies
func (f *WorkspacesModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &WorkspacesModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
