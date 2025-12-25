package modules

import (
	"log"
	"strings"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// WorkspacesModule displays workspace indicators
type WorkspacesModule struct {
	*statusbar.BaseModule
	widget         *gtk.Label
	workspaces     []string
	focusedIndex   int
	socketListener *statusbar.SocketEventListener
	socketPath     string
}

// NewWorkspacesModule creates a new workspaces module
func NewWorkspacesModule() *WorkspacesModule {
	return &WorkspacesModule{
		BaseModule:   statusbar.NewBaseModule("workspaces", statusbar.UpdateModeEventDriven),
		widget:       nil,
		workspaces:   []string{"1", "2", "3", "4", "5"},
		focusedIndex: 0,
		socketPath:   "",
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

	formatted := m.formatWorkspaces()
	label.SetText(formatted)

	return nil
}

// Initialize initializes the module with configuration
func (m *WorkspacesModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if path, ok := config["socket_path"].(string); ok {
		m.socketPath = path
	}

	if showLabels, ok := config["show_labels"].(bool); ok && !showLabels {
		m.widget.SetName("workspaces-icons")
	}

	m.SetCSSClasses([]string{"workspaces-module"})

	return nil
}

// SetupEventListeners sets up socket event listeners
func (m *WorkspacesModule) SetupEventListeners() ([]statusbar.EventListener, error) {
	if m.socketPath == "" {
		log.Printf("WorkspacesModule: No socket path configured, skipping event listener setup")
		return nil, nil
	}

	listener := statusbar.NewSocketEventListener(m.socketPath)
	listener.SetEventHandler(m.handleSocketEvent)

	m.socketListener = listener

	return []statusbar.EventListener{listener}, nil
}

// handleSocketEvent handles socket events
func (m *WorkspacesModule) handleSocketEvent(event string) {
	lines := strings.Split(event, "\n")
	for _, line := range lines {
		if strings.Contains(line, "workspace") {
			m.handleWorkspaceEvent(line)
		}
	}
}

// handleWorkspaceEvent handles a workspace event
func (m *WorkspacesModule) handleWorkspaceEvent(event string) {
	if strings.Contains(event, "focused") {
		parts := strings.Fields(event)
		for i, part := range parts {
			if part == "workspace" && i+1 < len(parts) {
				workspaceNum := parts[i+1]
				for idx, ws := range m.workspaces {
					if ws == workspaceNum {
						m.focusedIndex = idx
						break
					}
				}
			}
		}
	}
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

// Cleanup cleans up resources
func (m *WorkspacesModule) Cleanup() error {
	if m.socketListener != nil {
		m.socketListener.Cleanup()
		m.socketListener = nil
	}
	return m.BaseModule.Cleanup()
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
		"socket_path": "",
		"show_labels": true,
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
