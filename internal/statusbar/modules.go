package statusbar

import (
	"time"

	"github.com/sigma/locus-go/internal/config"
	"github.com/sigma/locus-go/internal/core"
)

// UpdateMode represents how a module updates
type UpdateMode int

const (
	UpdateModeStatic UpdateMode = iota
	UpdateModePeriodic
	UpdateModeEventDriven
	UpdateModeOnDemand
)

// Module is the interface that all status bar modules must implement
type Module interface {
	Name() string
	UpdateMode() UpdateMode
	UpdateInterval() time.Duration
	CreateWidget() interface{}
	Update(widget interface{})
	Cleanup()
	GetStyles() string
	HandlesClicks() bool
	HandleClick(widget interface{}) bool
	HandlesIPC() bool
	HandleIPC(message string) bool
}

// SimpleModule is a base implementation for simple modules
type SimpleModule struct {
	name       string
	updateMode UpdateMode
	interval   time.Duration
	styles     string
}

func (m *SimpleModule) Name() string                        { return m.name }
func (m *SimpleModule) UpdateMode() UpdateMode              { return m.updateMode }
func (m *SimpleModule) UpdateInterval() time.Duration       { return m.interval }
func (m *SimpleModule) GetStyles() string                   { return m.styles }
func (m *SimpleModule) HandlesClicks() bool                 { return false }
func (m *SimpleModule) HandleClick(widget interface{}) bool { return false }
func (m *SimpleModule) HandlesIPC() bool                    { return false }
func (m *SimpleModule) HandleIPC(message string) bool       { return false }
func (m *SimpleModule) Cleanup()                            {}

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

func (m *TimeModule) CreateWidget() interface{} {
	return &struct {
		Type  string
		Value string
	}{
		Type:  "label",
		Value: time.Now().Format(m.format),
	}
}

func (m *TimeModule) Update(widget interface{}) {
	if w, ok := widget.(*struct {
		Type  string
		Value string
	}); ok {
		w.Value = time.Now().Format(m.format)
	}
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

func (m *BatteryModule) CreateWidget() interface{} {
	return &struct {
		Type  string
		Value string
	}{
		Type:  "label",
		Value: "100%",
	}
}

func (m *BatteryModule) Update(widget interface{}) {
	// TODO: Read from /sys/class/power_supply/
	if w, ok := widget.(*struct {
		Type  string
		Value string
	}); ok {
		w.Value = "100%"
	}
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

func (m *WorkspacesModule) CreateWidget() interface{} {
	return &struct {
		Type  string
		Value string
	}{
		Type:  "label",
		Value: "1 2 3 4",
	}
}

func (m *WorkspacesModule) Update(widget interface{}) {
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

func (m *BindingModeModule) CreateWidget() interface{} {
	return &struct {
		Type  string
		Value string
	}{
		Type:  "label",
		Value: "",
	}
}

func (m *BindingModeModule) Update(widget interface{}) {
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

func (m *EmacsClockModule) CreateWidget() interface{} {
	return &struct {
		Type  string
		Value string
	}{
		Type:  "label",
		Value: m.fallbackText,
	}
}

func (m *EmacsClockModule) Update(widget interface{}) {
	// TODO: Query Emacs server
	if w, ok := widget.(*struct {
		Type  string
		Value string
	}); ok {
		w.Value = m.fallbackText
	}
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

func (m *CustomMessageModule) CreateWidget() interface{} {
	return &struct {
		Type  string
		Value string
	}{
		Type:  "label",
		Value: m.message,
	}
}

func (m *CustomMessageModule) Update(widget interface{}) {
	if w, ok := widget.(*struct {
		Type  string
		Value string
	}); ok {
		w.Value = m.message
	}
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
	count int
}

func NewNotificationModule(cfg *config.Config) *NotificationModule {
	return &NotificationModule{
		SimpleModule: SimpleModule{
			name:       "notifications",
			updateMode: UpdateModeEventDriven,
			interval:   0,
			styles:     "#notification-label { padding: 0 4px; }",
		},
		count: 0,
	}
}

func (m *NotificationModule) CreateWidget() interface{} {
	icon := "N"
	if cfg.Notification.UI.Icon != "" {
		icon = cfg.Notification.UI.Icon
	}

	return &struct {
		Type  string
		Value string
	}{
		Type:  "label",
		Value: icon,
	}
}

func (m *NotificationModule) Update(widget interface{}) {
	// Display count or icon
	// This would be updated by notification store events
}

func (m *NotificationModule) SetCount(count int) {
	m.count = count
}

// LauncherModule - launcher trigger button
type LauncherModule struct {
	SimpleModule
	bar *core.StatusBar
}

func NewLauncherModule(bar *core.StatusBar) *LauncherModule {
	return &LauncherModule{
		SimpleModule: SimpleModule{
			name:       "launcher",
			updateMode: UpdateModeStatic,
			interval:   0,
			styles:     "#launcher-module { padding: 0 4px; }",
		},
		bar: bar,
	}
}

func (m *LauncherModule) CreateWidget() interface{} {
	return &struct {
		Type  string
		Value string
	}{
		Type:  "button",
		Value: "Launcher",
	}
}

func (m *LauncherModule) Update(widget interface{}) {}

func (m *LauncherModule) HandlesClicks() bool {
	return true
}

func (m *LauncherModule) HandleClick(widget interface{}) bool {
	// Trigger launcher presentation
	if m.bar != nil {
		// TODO: Call app.PresentLauncher()
	}
	return true
}
