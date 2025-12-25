package modules

import (
	"log"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// LauncherCallback interface for launcher actions
type LauncherCallback interface {
	PresentLauncher() error
	HideLauncher() error
}

// LauncherModule displays launcher trigger button
type LauncherModule struct {
	*statusbar.BaseModule
	callback LauncherCallback
	widget   *gtk.Button
	label    string
}

// NewLauncherModule creates a new launcher module
func NewLauncherModule(callback LauncherCallback) *LauncherModule {
	return &LauncherModule{
		BaseModule: statusbar.NewBaseModule("launcher", statusbar.UpdateModeStatic),
		callback:   callback,
		widget:     nil,
		label:      "Launcher",
	}
}

// CreateWidget creates a launcher button widget
func (m *LauncherModule) CreateWidget() (gtk.IWidget, error) {
	button, err := gtk.ButtonNewWithLabel(m.label)
	if err != nil {
		return nil, err
	}

	button.SetRelief(gtk.RELIEF_NONE)
	m.widget = button

	helper := &statusbar.WidgetHelper{}
	if err := helper.ApplyStylesToWidget(button, m.GetStyles(), m.GetCSSClasses()); err != nil {
		return nil, err
	}

	button.Connect("clicked", func() {
		m.HandleClick(button)
	})

	return button, nil
}

// UpdateWidget is not needed for static launcher module
func (m *LauncherModule) UpdateWidget(widget gtk.IWidget) error {
	return nil
}

// Initialize initializes the module with configuration
func (m *LauncherModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if label, ok := config["label"].(string); ok {
		m.label = label
	}

	m.SetCSSClasses([]string{"launcher-module", "launcher-button"})

	m.SetClickHandler(func(widget gtk.IWidget) bool {
		if m.callback != nil {
			log.Printf("Launcher button clicked")
			if err := m.callback.PresentLauncher(); err != nil {
				log.Printf("Failed to present launcher: %v", err)
			}
		}
		return true
	})

	return nil
}

// SetCallback sets the launcher callback
func (m *LauncherModule) SetCallback(callback LauncherCallback) {
	m.callback = callback
}

// LauncherModuleFactory is a factory for creating LauncherModule instances
type LauncherModuleFactory struct {
	callback LauncherCallback
}

// NewLauncherModuleFactory creates a new launcher module factory
func NewLauncherModuleFactory(callback LauncherCallback) *LauncherModuleFactory {
	return &LauncherModuleFactory{
		callback: callback,
	}
}

// CreateModule creates a new LauncherModule instance
func (f *LauncherModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewLauncherModule(f.callback)
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns the module name
func (f *LauncherModuleFactory) ModuleName() string {
	return "launcher"
}

// DefaultConfig returns default configuration
func (f *LauncherModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"label":       "Launcher",
		"css_classes": []string{"launcher-module", "launcher-button"},
	}
}

// Dependencies returns module dependencies
func (f *LauncherModuleFactory) Dependencies() []string {
	return []string{}
}

// RegisterLauncherFactory registers the launcher module factory with a callback
func RegisterLauncherFactory(callback LauncherCallback) error {
	registry := statusbar.DefaultRegistry()
	factory := NewLauncherModuleFactory(callback)
	return registry.RegisterFactory(factory)
}
