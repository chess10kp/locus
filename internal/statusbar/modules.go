package statusbar

import (
	"time"

	"github.com/sigma/locus-go/internal/config"
)

// WidgetType represents the type of widget
type WidgetType string

const (
	WidgetTypeLabel  WidgetType = "label"
	WidgetTypeButton WidgetType = "button"
	WidgetTypeImage  WidgetType = "image"
	WidgetTypeBox    WidgetType = "box"
)

// String returns the string representation
func (w WidgetType) String() string {
	return string(w)
}

// Widget represents a status bar widget
type Widget struct {
	Type  WidgetType
	Value string
}

// SimpleModule is a base implementation for simple modules
type SimpleModule struct {
	name       string
	updateMode UpdateMode
	interval   time.Duration
	styles     string
}

func (m *SimpleModule) Name() string                    { return m.name }
func (m *SimpleModule) UpdateMode() UpdateMode          { return m.updateMode }
func (m *SimpleModule) UpdateInterval() time.Duration   { return m.interval }
func (m *SimpleModule) GetStyles() string               { return m.styles }
func (m *SimpleModule) HandlesClicks() bool             { return false }
func (m *SimpleModule) HandleClick(widget *Widget) bool { return false }
func (m *SimpleModule) HandlesIPC() bool                { return false }
func (m *SimpleModule) HandleIPC(message string) bool   { return false }
func (m *SimpleModule) Cleanup()                        {}

// TimeModule - displays current time
type TimeModule struct {
	SimpleModule
	format string
}

func NewTimeModule(cfg *config.Config) *TimeModule {
	format := "%H:%M"
	if moduleCfg, ok := cfg.StatusBar.ModuleConfigs["time"]; ok {
		format = moduleCfg.Format
	}

	return &TimeModule{
		SimpleModule: SimpleModule{
			name:       "time",
			updateMode: UpdateModePeriodic,
			interval:   time.Minute,
			styles:     "#time-label { font-size: 14px; padding: 0 8px; }",
		},
		format: format,
	}
}

func (m *TimeModule) CreateWidget() *Widget {
	return &Widget{
		Type:  WidgetTypeLabel,
		Value: time.Now().Format(m.format),
	}
}

func (m *TimeModule) Update(widget *Widget) {
	widget.Value = time.Now().Format(m.format)
}

// BatteryModule - displays battery status
type BatteryModule struct {
	SimpleModule
}

func NewBatteryModule() *BatteryModule {
	return &BatteryModule{
		SimpleModule: SimpleModule{
			name:       "battery",
			updateMode: UpdateModePeriodic,
			interval:   time.Minute,
			styles:     "#battery-label { padding: 0 8px; }",
		},
	}
}

func (m *BatteryModule) CreateWidget() *Widget {
	return &Widget{
		Type:  WidgetTypeLabel,
		Value: "100%",
	}
}

func (m *BatteryModule) Update(widget *Widget) {
	widget.Value = "100%"
}

// WorkspacesModule - displays workspace indicators
type WorkspacesModule struct {
	SimpleModule
}

func NewWorkspacesModule() *WorkspacesModule {
	return &WorkspacesModule{
		SimpleModule: SimpleModule{
			name:       "workspaces",
			updateMode: UpdateModeEventDriven,
			interval:   0,
			styles:     "#workspaces-label { padding: 0 4px; }",
		},
	}
}

func (m *WorkspacesModule) CreateWidget() *Widget {
	return &Widget{
		Type:  WidgetTypeLabel,
		Value: "1 2 3 4",
	}
}

func (m *WorkspacesModule) Update(widget *Widget) {
	// TODO: Get workspaces from WM client
}

// BindingModeModule - displays Sway binding mode
type BindingModeModule struct {
	SimpleModule
}

func NewBindingModeModule() *BindingModeModule {
	return &BindingModeModule{
		SimpleModule: SimpleModule{
			name:       "binding_mode",
			updateMode: UpdateModeEventDriven,
			interval:   time.Second,
			styles:     "#binding-mode-label { padding: 0 4px; }",
		},
	}
}

func (m *BindingModeModule) CreateWidget() *Widget {
	return &Widget{
		Type:  WidgetTypeLabel,
		Value: "",
	}
}

func (m *BindingModeModule) Update(widget *Widget) {
	// TODO: Get binding mode from WM client
}

// EmacsClockModule - displays Emacs org-mode clock
type EmacsClockModule struct {
	SimpleModule
	fallbackText string
}

func NewEmacsClockModule(cfg *config.Config) *EmacsClockModule {
	return &EmacsClockModule{
		SimpleModule: SimpleModule{
			name:       "emacs_clock",
			updateMode: UpdateModePeriodic,
			interval:   10 * time.Second,
			styles:     "#emacs-clock-label { padding: 0 4px; }",
		},
		fallbackText: "Not clocked in",
	}
}

func (m *EmacsClockModule) CreateWidget() *Widget {
	return &Widget{
		Type:  WidgetTypeLabel,
		Value: m.fallbackText,
	}
}

func (m *EmacsClockModule) Update(widget *Widget) {
	widget.Value = m.fallbackText
}

// CustomMessageModule - displays custom messages via IPC
type CustomMessageModule struct {
	SimpleModule
	message string
}

func NewCustomMessageModule() *CustomMessageModule {
	return &CustomMessageModule{
		SimpleModule: SimpleModule{
			name:       "custom_message",
			updateMode: UpdateModeOnDemand,
			interval:   0,
			styles:     "#custom-message-label { padding: 0 4px; }",
		},
		message: "",
	}
}

func (m *CustomMessageModule) CreateWidget() *Widget {
	return &Widget{
		Type:  WidgetTypeLabel,
		Value: m.message,
	}
}

func (m *CustomMessageModule) Update(widget *Widget) {
	widget.Value = m.message
}

func (m *CustomMessageModule) HandlesIPC() bool {
	return true
}

func (m *CustomMessageModule) HandleIPC(message string) bool {
	m.message = message
	return true
}

// NotificationModule - displays notification count
type NotificationModule struct {
	SimpleModule
	count  int
	config *config.Config
}

func NewNotificationModule(cfg *config.Config) *NotificationModule {
	return &NotificationModule{
		SimpleModule: SimpleModule{
			name:       "notifications",
			updateMode: UpdateModeEventDriven,
			interval:   0,
			styles:     "#notification-label { padding: 0 4px; }",
		},
		count:  0,
		config: cfg,
	}
}

func (m *NotificationModule) CreateWidget() *Widget {
	icon := "N"
	if m.config != nil && m.config.Notification.UI.Icon != "" {
		icon = m.config.Notification.UI.Icon
	}

	return &Widget{
		Type:  WidgetTypeLabel,
		Value: icon,
	}
}

func (m *NotificationModule) Update(widget *Widget) {
	// Display count or icon
	// This would be updated by notification store events
}

func (m *NotificationModule) SetCount(count int) {
	m.count = count
}
