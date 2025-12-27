package modules

import (
	"time"

	"github.com/gotk3/gotk3/gtk"
	"github.com/chess10kp/locus/internal/statusbar"
)

// TimeModule displays current time
type TimeModule struct {
	*statusbar.BaseModule
	format string
	widget *gtk.Label
}

// NewTimeModule creates a new time module
func NewTimeModule() *TimeModule {
	return &TimeModule{
		BaseModule: statusbar.NewBaseModule("time", statusbar.UpdateModePeriodic),
		format:     "15:04:05",
		widget:     nil,
	}
}

// CreateWidget creates the time widget
func (m *TimeModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(time.Now().Format(m.format))
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

// UpdateWidget updates the time widget
func (m *TimeModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	currentTime := time.Now().Format(m.format)
	label.SetText(currentTime)

	return nil
}

// Initialize initializes the module with configuration
func (m *TimeModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if format, ok := config["format"].(string); ok {
		m.format = format
	}

	m.SetCSSClasses([]string{"time-module"})

	return nil
}

// TimeModuleFactory is a factory for creating TimeModule instances
type TimeModuleFactory struct{}

// CreateModule creates a new TimeModule instance
func (f *TimeModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewTimeModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns the module name
func (f *TimeModuleFactory) ModuleName() string {
	return "time"
}

// DefaultConfig returns default configuration
func (f *TimeModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"format":      "15:04:05",
		"interval":    "1s",
		"css_classes": []string{"time-module"},
	}
}

// Dependencies returns module dependencies
func (f *TimeModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &TimeModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
