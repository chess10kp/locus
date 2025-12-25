package modules

import (
	"log"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// CustomMessageModule displays custom messages via IPC
type CustomMessageModule struct {
	*statusbar.BaseModule
	widget  *gtk.Label
	message string
	timeout int
}

// NewCustomMessageModule creates a new custom message module
func NewCustomMessageModule() *CustomMessageModule {
	return &CustomMessageModule{
		BaseModule: statusbar.NewBaseModule("custom_message", statusbar.UpdateModeOnDemand),
		widget:     nil,
		message:    "",
		timeout:    5,
	}
}

// CreateWidget creates a custom message label widget
func (m *CustomMessageModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.message)
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

// UpdateWidget updates custom message widget
func (m *CustomMessageModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	label.SetText(m.message)

	return nil
}

// Initialize initializes the module with configuration
func (m *CustomMessageModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if message, ok := config["message"].(string); ok {
		m.message = message
	}

	if timeout, ok := config["timeout"].(int); ok {
		m.timeout = timeout
	}

	m.SetCSSClasses([]string{"custom-message-module"})

	m.SetIPCHandler(func(message string) bool {
		log.Printf("CustomMessageModule received IPC: %s", message)
		m.message = message
		return true
	})

	return nil
}

// SetMessage sets the custom message
func (m *CustomMessageModule) SetMessage(message string) {
	m.message = message
}

// GetMessage returns the current message
func (m *CustomMessageModule) GetMessage() string {
	return m.message
}

// Cleanup cleans up resources
func (m *CustomMessageModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// CustomMessageModuleFactory is a factory for creating CustomMessageModule instances
type CustomMessageModuleFactory struct{}

// CreateModule creates a new CustomMessageModule instance
func (f *CustomMessageModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewCustomMessageModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns the module name
func (f *CustomMessageModuleFactory) ModuleName() string {
	return "custom_message"
}

// DefaultConfig returns the default configuration
func (f *CustomMessageModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"message":     "",
		"timeout":     5,
		"css_classes": []string{"custom-message-module"},
	}
}

// Dependencies returns the module dependencies
func (f *CustomMessageModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &CustomMessageModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
