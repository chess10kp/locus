package modules

import (
	"fmt"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// NotificationModule displays notification count with icon
type NotificationModule struct {
	*statusbar.BaseModule
	widget   *gtk.Button
	count    int
	icon     string
	iconFull string
}

// NewNotificationModule creates a new notification module
func NewNotificationModule() *NotificationModule {
	return &NotificationModule{
		BaseModule: statusbar.NewBaseModule("notifications", statusbar.UpdateModeEventDriven),
		widget:     nil,
		count:      0,
		icon:       "N",
		iconFull:   "N",
	}
}

// CreateWidget creates a notification button widget
func (m *NotificationModule) CreateWidget() (gtk.IWidget, error) {
	button, err := gtk.ButtonNewWithLabel(m.formatNotification())
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

// UpdateWidget updates notification widget
func (m *NotificationModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	button, ok := widget.(*gtk.Button)
	if !ok {
		return nil
	}

	button.SetLabel(m.formatNotification())

	return nil
}

// Initialize initializes the module with configuration
func (m *NotificationModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if icon, ok := config["icon"].(string); ok {
		m.icon = icon
	}

	if iconFull, ok := config["icon_full"].(string); ok {
		m.iconFull = iconFull
	}

	if count, ok := config["count"].(int); ok {
		m.count = count
	}

	m.SetCSSClasses([]string{"notification-module", "notification-button"})

	m.SetClickHandler(func(widget gtk.IWidget) bool {
		return true
	})

	return nil
}

// formatNotification formats the notification text for display
func (m *NotificationModule) formatNotification() string {
	if m.count > 0 {
		if m.count > 99 {
			return fmt.Sprintf("%s 99+", m.iconFull)
		}
		return fmt.Sprintf("%s %d", m.iconFull, m.count)
	}
	return ""
}

// SetCount sets the unread notification count
func (m *NotificationModule) SetCount(count int) {
	m.count = count
}

// GetCount returns the current unread count
func (m *NotificationModule) GetCount() int {
	return m.count
}

// IncrementCount increments the unread notification count
func (m *NotificationModule) IncrementCount() {
	m.count++
}

// DecrementCount decrements the unread notification count
func (m *NotificationModule) DecrementCount() {
	if m.count > 0 {
		m.count--
	}
}

// ClearCount clears the unread notification count
func (m *NotificationModule) ClearCount() {
	m.count = 0
}

// SetIcon sets the notification icon
func (m *NotificationModule) SetIcon(icon string) {
	m.icon = icon
}

// SetIconFull sets the full notification icon (used when there are unread notifications)
func (m *NotificationModule) SetIconFull(icon string) {
	m.iconFull = icon
}

// Cleanup cleans up resources
func (m *NotificationModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// NotificationModuleFactory is a factory for creating NotificationModule instances
type NotificationModuleFactory struct{}

// CreateModule creates a new NotificationModule instance
func (f *NotificationModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewNotificationModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *NotificationModuleFactory) ModuleName() string {
	return "notifications"
}

// DefaultConfig returns default configuration
func (f *NotificationModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"icon":        "N",
		"icon_full":   "N",
		"count":       0,
		"css_classes": []string{"notification-module", "notification-button"},
	}
}

// Dependencies returns module dependencies
func (f *NotificationModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &NotificationModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
