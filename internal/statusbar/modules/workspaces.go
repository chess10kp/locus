package modules

import (
	"context"
	"encoding/json"
	"fmt"
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
	Num     int    `json:"num"`
	Output  string `json:"output"`
}

// getWorkspacesFromSway gets workspaces from sway IPC
func getWorkspacesFromSway() ([]Workspace, error) {
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
	swayClient   sway.Client
	ctx          context.Context
	cancel       context.CancelFunc
}

// SwayEventListener handles sway workspace events
type SwayEventListener struct {
	client  sway.Client
	ctx     context.Context
	cancel  context.CancelFunc
	handler func(sway.Event)
	running bool
}

func NewSwayEventListener() *SwayEventListener {
	ctx, cancel := context.WithCancel(context.Background())
	return &SwayEventListener{
		ctx:     ctx,
		cancel:  cancel,
		running: false,
	}
}

func (l *SwayEventListener) SetHandler(handler func(sway.Event)) {
	l.handler = handler
}

func (l *SwayEventListener) Start(callback func()) error {
	if l.running {
		return fmt.Errorf("sway event listener is already running")
	}

	client, err := sway.New(l.ctx)
	if err != nil {
		return fmt.Errorf("failed to connect to sway: %w", err)
	}

	l.client = client

	recv, err := client.Subscribe(l.ctx, sway.EventTypeWorkspace)
	if err != nil {
		return fmt.Errorf("failed to subscribe to workspace events: %w", err)
	}

	l.running = true

	go func() {
		defer func() { l.running = false }()
		for {
			select {
			case <-l.ctx.Done():
				return
			case event := <-recv:
				if l.handler != nil {
					l.handler(event)
				}
				if callback != nil {
					callback()
				}
			}
		}
	}()

	return nil
}

func (l *SwayEventListener) Stop() error {
	l.cancel()
	l.running = false
	return nil
}

func (l *SwayEventListener) Cleanup() {
	l.Stop()
}

func (l *SwayEventListener) IsRunning() bool {
	return l.running
}

// NewWorkspacesModule creates a new workspaces module
func NewWorkspacesModule() *WorkspacesModule {
	ctx, cancel := context.WithCancel(context.Background())
	return &WorkspacesModule{
		BaseModule:   statusbar.NewBaseModule("workspaces", statusbar.UpdateModeEventDriven),
		widget:       nil,
		workspaces:   []string{"1", "2", "3", "4", "5"},
		focusedIndex: 0,
		swayClient:   nil,
		ctx:          ctx,
		cancel:       cancel,
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
				m.focusedIndex = i
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

// SetupEventListeners sets up sway event listeners
func (m *WorkspacesModule) SetupEventListeners() ([]statusbar.EventListener, error) {
	client, err := sway.New(m.ctx)
	if err != nil {
		log.Printf("WorkspacesModule: Failed to connect to sway: %v", err)
		return nil, err
	}

	m.swayClient = client

	// Subscribe to workspace events
	recv, err := client.Subscribe(m.ctx, sway.EventTypeWorkspace)
	if err != nil {
		log.Printf("WorkspacesModule: Failed to subscribe to workspace events: %v", err)
		return nil, err
	}

	// Start listening in a goroutine
	go func() {
		for {
			select {
			case <-m.ctx.Done():
				return
			case event := <-recv:
				m.handleWorkspaceEvent(event)
			}
		}
	}()

	// Also create a custom event listener for cleanup
	return []statusbar.EventListener{m}, nil
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
		"interval":    "5s",
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
