package modules

import (
	"time"

	"github.com/gotk3/gotk3/glib"
	"github.com/gotk3/gotk3/gtk"
	"github.com/chess10kp/locus/internal/config"
	"github.com/chess10kp/locus/internal/notification"
	"github.com/chess10kp/locus/internal/statusbar"
)

type NotificationModule struct {
	*statusbar.BaseModule
	widget       *gtk.Button
	count        int
	icon         string
	iconFull     string
	socketPath   string
	updateTicker *time.Ticker
	running      bool
}

func NewNotificationModule(cfg *config.Config) *NotificationModule {
	socketPath := normalizeSocketPath(cfg.Notification.History.PersistPath)

	return &NotificationModule{
		BaseModule:   statusbar.NewBaseModule("notifications", statusbar.UpdateModePeriodic),
		widget:       nil,
		count:        0,
		icon:         "N",
		iconFull:     "N",
		socketPath:   socketPath,
		updateTicker: time.NewTicker(5 * time.Second),
		running:      false,
	}
}

func normalizeSocketPath(path string) string {
	return path + ".sock"
}

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

func (m *NotificationModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	button, ok := widget.(*gtk.Button)
	if !ok {
		return nil
	}

	count := m.fetchUnreadCount()
	if count != m.count {
		m.count = count
		button.SetLabel(m.formatNotification())
	}

	return nil
}

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

	if socketPath, ok := config["socket_path"].(string); ok {
		m.socketPath = socketPath
	}

	m.SetCSSClasses([]string{"notification-module", "notification-button"})

	m.SetClickHandler(func(widget gtk.IWidget) bool {
		return true
	})

	return nil
}

func (m *NotificationModule) Cleanup() error {
	if m.updateTicker != nil {
		m.updateTicker.Stop()
		m.running = false
	}
	return m.BaseModule.Cleanup()
}

func (m *NotificationModule) StartUpdates(callback func()) {
	if !m.running {
		m.running = true
		go m.updateLoop(callback)
	}
}

func (m *NotificationModule) StopUpdates() {
	m.running = false
	if m.updateTicker != nil {
		m.updateTicker.Stop()
	}
}

func (m *NotificationModule) updateLoop(callback func()) {
	for m.running {
		select {
		case <-m.updateTicker.C:
			glib.IdleAdd(func() {
				if m.widget != nil {
					count := m.fetchUnreadCount()
					if count != m.count {
						m.count = count
						m.widget.SetLabel(m.formatNotification())
					}
				}
			})
		}
	}
}

func (m *NotificationModule) fetchUnreadCount() int {
	count, err := notification.GetUnreadCount(m.socketPath)
	if err != nil {
		return 0
	}
	return count
}
func (m *NotificationModule) formatNotification() string {
	if m.count > 0 {
		if m.count > 99 {
			return m.iconFull + " 99+"
		}
		return m.iconFull + " " + intToString(m.count)
	}
	return ""
}

func intToString(n int) string {
	if n < 0 {
		return "0"
	}
	if n < 10 {
		return string('0' + rune(n))
	}
	result := ""
	for n > 0 {
		result = string('0'+rune(n%10)) + result
		n = n / 10
	}
	return result
}

func (m *NotificationModule) SetCount(count int) {
	m.count = count
}

func (m *NotificationModule) GetCount() int {
	return m.count
}

type NotificationModuleFactory struct {
	config *config.Config
}

func NewNotificationModuleFactory(cfg *config.Config) *NotificationModuleFactory {
	return &NotificationModuleFactory{
		config: cfg,
	}
}

func (f *NotificationModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewNotificationModule(f.config)
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

func (f *NotificationModuleFactory) ModuleName() string {
	return "notifications"
}

func (f *NotificationModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"icon":        "N",
		"icon_full":   "N",
		"css_classes": []string{"notification-module", "notification-button"},
	}
}

func (f *NotificationModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &NotificationModuleFactory{
		config: &config.DefaultConfig,
	}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
