package modules

import (
	"encoding/json"
	"log"
	"os"
	"os/exec"
	"strings"
	"time"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// BindingModeResult represents the result from swaymsg/scrollmsg
type BindingModeResult struct {
	Name string `json:"name"`
}

// getBindingModeFromWM gets the current binding mode from the window manager
func getBindingModeFromWM() (string, error) {
	env := os.Environ()
	for i, e := range env {
		if strings.HasPrefix(e, "LD_PRELOAD=") {
			env = append(env[:i], env[i+1:]...)
			break
		}
	}

	cmd := exec.Command("scrollmsg", "-t", "get_binding_state")
	cmd.Env = env
	output, err := cmd.Output()
	if err == nil {
		var result BindingModeResult
		if err := json.Unmarshal(output, &result); err == nil {
			return result.Name, nil
		}
	}

	cmd = exec.Command("swaymsg", "-t", "get_binding_mode")
	cmd.Env = env
	output, err = cmd.Output()
	if err != nil {
		return "", err
	}

	var result BindingModeResult
	if err := json.Unmarshal(output, &result); err != nil {
		return "", err
	}

	return result.Name, nil
}

// BindingModeModule displays the current window manager binding mode
type BindingModeModule struct {
	*statusbar.BaseModule
	widget      *gtk.Label
	currentMode string
	visible     bool
	interval    time.Duration
}

// NewBindingModeModule creates a new binding mode module
func NewBindingModeModule() *BindingModeModule {
	return &BindingModeModule{
		BaseModule:  statusbar.NewBaseModule("binding_mode", statusbar.UpdateModePeriodic),
		widget:      nil,
		currentMode: "",
		visible:     false,
		interval:    time.Second,
	}
}

// CreateWidget creates a binding mode label widget
func (m *BindingModeModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew("")
	if err != nil {
		return nil, err
	}

	m.widget = label

	helper := &statusbar.WidgetHelper{}
	if err := helper.ApplyStylesToWidget(label, m.GetStyles(), m.GetCSSClasses()); err != nil {
		return nil, err
	}

	m.widget.SetVisible(false)

	return label, nil
}

// UpdateWidget updates binding mode widget
func (m *BindingModeModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	mode, err := getBindingModeFromWM()
	if err != nil {
		log.Printf("Failed to get binding mode: %v", err)
		label.SetText("")
		label.SetVisible(false)
		return nil
	}

	if mode != "" && mode != "default" {
		m.currentMode = mode
		label.SetText("[" + mode + "]")
		label.SetVisible(true)
		m.visible = true
	} else {
		m.currentMode = ""
		label.SetText("")
		label.SetVisible(false)
		m.visible = false
	}

	return nil
}

// Initialize initializes the module with configuration
func (m *BindingModeModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if interval, ok := config["interval"].(string); ok {
		if duration, err := time.ParseDuration(interval); err == nil {
			m.interval = duration
		}
	}

	m.SetCSSClasses([]string{"binding-mode-module"})

	return nil
}

// GetCurrentMode returns the current binding mode
func (m *BindingModeModule) GetCurrentMode() string {
	return m.currentMode
}

// IsVisible returns whether the binding mode is currently visible
func (m *BindingModeModule) IsVisible() bool {
	return m.visible
}

// Cleanup cleans up resources
func (m *BindingModeModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// BindingModeModuleFactory is a factory for creating BindingModeModule instances
type BindingModeModuleFactory struct{}

// CreateModule creates a new BindingModeModule instance
func (f *BindingModeModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewBindingModeModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *BindingModeModuleFactory) ModuleName() string {
	return "binding_mode"
}

// DefaultConfig returns default configuration
func (f *BindingModeModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"interval":    "1s",
		"css_classes": []string{"binding-mode-module"},
	}
}

// Dependencies returns module dependencies
func (f *BindingModeModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &BindingModeModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
