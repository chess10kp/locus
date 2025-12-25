package statusbar

import (
	"time"

	"github.com/gotk3/gotk3/gtk"
)

// UpdateMode represents how a module updates its content
type UpdateMode int

const (
	UpdateModeStatic UpdateMode = iota
	UpdateModePeriodic
	UpdateModeEventDriven
	UpdateModeOnDemand
)

// String returns the string representation of UpdateMode
func (u UpdateMode) String() string {
	switch u {
	case UpdateModeStatic:
		return "static"
	case UpdateModePeriodic:
		return "periodic"
	case UpdateModeEventDriven:
		return "event-driven"
	case UpdateModeOnDemand:
		return "on-demand"
	default:
		return "unknown"
	}
}

// Module is the interface that all status bar modules must implement
type Module interface {
	// Identification
	Name() string
	UpdateMode() UpdateMode
	UpdateInterval() time.Duration

	// Widget management - return actual GTK widgets
	CreateWidget() (gtk.IWidget, error)
	UpdateWidget(widget gtk.IWidget) error

	// Lifecycle
	Initialize(config map[string]interface{}) error
	Cleanup() error
	IsInitialized() bool

	// Events and interaction
	SetupEventListeners() ([]EventListener, error)
	HandlesClicks() bool
	HandleClick(widget gtk.IWidget) bool
	HandlesIPC() bool
	HandleIPC(message string) bool

	// Styling
	GetStyles() string
	GetCSSClasses() []string
}

// BaseModule provides a common base implementation for modules
type BaseModule struct {
	name         string
	updateMode   UpdateMode
	interval     time.Duration
	styles       string
	cssClasses   []string
	initialized  bool
	config       map[string]interface{}
	clickHandler func(widget gtk.IWidget) bool
	ipcHandler   func(message string) bool
}

// NewBaseModule creates a new base module with defaults
func NewBaseModule(name string, updateMode UpdateMode) *BaseModule {
	return &BaseModule{
		name:         name,
		updateMode:   updateMode,
		interval:     time.Second,
		styles:       "",
		cssClasses:   []string{},
		initialized:  false,
		config:       make(map[string]interface{}),
		clickHandler: nil,
		ipcHandler:   nil,
	}
}

// Name returns the module name
func (m *BaseModule) Name() string {
	return m.name
}

// UpdateMode returns the update mode
func (m *BaseModule) UpdateMode() UpdateMode {
	return m.updateMode
}

// UpdateInterval returns the update interval
func (m *BaseModule) UpdateInterval() time.Duration {
	return m.interval
}

// GetStyles returns CSS styles
func (m *BaseModule) GetStyles() string {
	return m.styles
}

// SetStyles sets CSS styles
func (m *BaseModule) SetStyles(styles string) {
	m.styles = styles
}

// GetCSSClasses returns CSS classes
func (m *BaseModule) GetCSSClasses() []string {
	return m.cssClasses
}

// SetCSSClasses sets CSS classes
func (m *BaseModule) SetCSSClasses(classes []string) {
	m.cssClasses = classes
}

// Initialize initializes the module with configuration
func (m *BaseModule) Initialize(config map[string]interface{}) error {
	m.config = config
	m.initialized = true

	if interval, ok := config["interval"].(string); ok {
		if duration, err := time.ParseDuration(interval); err == nil {
			m.interval = duration
		}
	}

	if interval, ok := config["interval"].(time.Duration); ok {
		m.interval = interval
	}

	if styles, ok := config["styles"].(string); ok {
		m.styles = styles
	}

	if classes, ok := config["css_classes"].([]string); ok {
		m.cssClasses = classes
	}

	return nil
}

// GetConfig returns the module configuration
func (m *BaseModule) GetConfig() map[string]interface{} {
	return m.config
}

// GetConfigValue returns a configuration value by key
func (m *BaseModule) GetConfigValue(key string, defaultValue interface{}) interface{} {
	if val, ok := m.config[key]; ok {
		return val
	}
	return defaultValue
}

// HandlesClicks returns whether the module handles click events
func (m *BaseModule) HandlesClicks() bool {
	return m.clickHandler != nil
}

// SetClickHandler sets the click handler
func (m *BaseModule) SetClickHandler(handler func(widget gtk.IWidget) bool) {
	m.clickHandler = handler
}

// HandleClick handles click events
func (m *BaseModule) HandleClick(widget gtk.IWidget) bool {
	if m.clickHandler != nil {
		return m.clickHandler(widget)
	}
	return false
}

// HandlesIPC returns whether the module handles IPC messages
func (m *BaseModule) HandlesIPC() bool {
	return m.ipcHandler != nil
}

// SetIPCHandler sets the IPC handler
func (m *BaseModule) SetIPCHandler(handler func(message string) bool) {
	m.ipcHandler = handler
}

// HandleIPC handles IPC messages
func (m *BaseModule) HandleIPC(message string) bool {
	if m.ipcHandler != nil {
		return m.ipcHandler(message)
	}
	return false
}

// SetupEventListeners sets up event listeners (base implementation returns nil)
func (m *BaseModule) SetupEventListeners() ([]EventListener, error) {
	return nil, nil
}

// Cleanup cleans up module resources (base implementation does nothing)
func (m *BaseModule) Cleanup() error {
	return nil
}

// IsInitialized returns whether the module has been initialized
func (m *BaseModule) IsInitialized() bool {
	return m.initialized
}

// WidgetHelper provides helper functions for widget styling
type WidgetHelper struct{}

// ApplyStylesToWidget applies CSS styles and classes to a widget
func (h *WidgetHelper) ApplyStylesToWidget(widget gtk.IWidget, styles string, classes []string) error {
	if widget == nil {
		return nil
	}

	// Set CSS classes
	if len(classes) > 0 {
		if cssWidget, ok := widget.(interface{ GetStyleContext() *gtk.StyleContext }); ok {
			ctx := cssWidget.GetStyleContext()
			for _, class := range classes {
				ctx.AddClass(class)
			}
		}
	}

	// Set inline styles if widget has SetName
	if styles != "" {
		if namedWidget, ok := widget.(interface{ SetName(string) }); ok {
			name, _ := widget.ToWidget().GetName()
			namedWidget.SetName(name)
		}
	}

	return nil
}

// ApplyCSSClasses applies CSS classes to a widget
func (h *WidgetHelper) ApplyCSSClasses(widget gtk.IWidget, classes []string) error {
	if widget == nil || len(classes) == 0 {
		return nil
	}

	if cssWidget, ok := widget.(interface{ GetStyleContext() *gtk.StyleContext }); ok {
		ctx := cssWidget.GetStyleContext()
		for _, class := range classes {
			ctx.AddClass(class)
		}
	}

	return nil
}

// CreateStyledLabel creates a styled label widget
func (h *WidgetHelper) CreateStyledLabel(text string, styles string, classes []string) (*gtk.Label, error) {
	label, err := gtk.LabelNew(text)
	if err != nil {
		return nil, err
	}

	if err := h.ApplyStylesToWidget(label, styles, classes); err != nil {
		return nil, err
	}

	return label, nil
}

// CreateStyledButton creates a styled button widget
func (h *WidgetHelper) CreateStyledButton(label string, styles string, classes []string) (*gtk.Button, error) {
	button, err := gtk.ButtonNewWithLabel(label)
	if err != nil {
		return nil, err
	}

	if err := h.ApplyStylesToWidget(button, styles, classes); err != nil {
		return nil, err
	}

	return button, nil
}

// CreateStyledBox creates a styled box widget
func (h *WidgetHelper) CreateStyledBox(orientation gtk.Orientation, spacing int, styles string, classes []string) (*gtk.Box, error) {
	box, err := gtk.BoxNew(orientation, spacing)
	if err != nil {
		return nil, err
	}

	if err := h.ApplyStylesToWidget(box, styles, classes); err != nil {
		return nil, err
	}

	return box, nil
}

// CreateStyledImage creates a styled image widget
func (h *WidgetHelper) CreateStyledImage(iconName string, size int, styles string, classes []string) (*gtk.Image, error) {
	image, err := gtk.ImageNewFromIconName(iconName, gtk.ICON_SIZE_MENU)
	if err != nil {
		return nil, err
	}

	if err := h.ApplyStylesToWidget(image, styles, classes); err != nil {
		return nil, err
	}

	return image, nil
}

// CreateStyledEventBox creates a styled event box widget
func (h *WidgetHelper) CreateStyledEventBox(styles string, classes []string) (*gtk.EventBox, error) {
	box, err := gtk.EventBoxNew()
	if err != nil {
		return nil, err
	}

	if err := h.ApplyStylesToWidget(box, styles, classes); err != nil {
		return nil, err
	}

	return box, nil
}
