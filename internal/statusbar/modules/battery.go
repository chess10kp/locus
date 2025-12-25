package modules

import (
	"fmt"
	"os"
	"strconv"
	"strings"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// BatteryModule displays battery status
type BatteryModule struct {
	*statusbar.BaseModule
	widget         *gtk.Label
	batteryPath    string
	showPercentage bool
	showIcon       bool
	percentage     int
	isCharging     bool
}

// NewBatteryModule creates a new battery module
func NewBatteryModule() *BatteryModule {
	return &BatteryModule{
		BaseModule:     statusbar.NewBaseModule("battery", statusbar.UpdateModePeriodic),
		widget:         nil,
		batteryPath:    "/sys/class/power_supply/BAT0/capacity",
		showPercentage: true,
		showIcon:       true,
		percentage:     100,
		isCharging:     false,
	}
}

// CreateWidget creates a battery label widget
func (m *BatteryModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.formatBattery())
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

// UpdateWidget updates battery widget
func (m *BatteryModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	m.readBatteryStatus()
	formatted := m.formatBattery()
	label.SetText(formatted)

	return nil
}

// Initialize initializes the module with configuration
func (m *BatteryModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if path, ok := config["battery_path"].(string); ok {
		m.batteryPath = path
	}

	if showPercentage, ok := config["show_percentage"].(bool); ok {
		m.showPercentage = showPercentage
	}

	if showIcon, ok := config["show_icon"].(bool); ok {
		m.showIcon = showIcon
	}

	m.SetCSSClasses([]string{"battery-module"})

	m.readBatteryStatus()

	return nil
}

// readBatteryStatus reads battery status from system
func (m *BatteryModule) readBatteryStatus() {
	data, err := os.ReadFile(m.batteryPath)
	if err != nil {
		m.percentage = 100
		return
	}

	percentageStr := strings.TrimSpace(string(data))
	m.percentage, err = strconv.Atoi(percentageStr)
	if err != nil {
		m.percentage = 100
	}

	statusPath := strings.Replace(m.batteryPath, "capacity", "status", 1)
	statusData, err := os.ReadFile(statusPath)
	if err == nil {
		status := strings.TrimSpace(string(statusData))
		m.isCharging = status == "Charging"
	}
}

// formatBattery formats battery status for display
func (m *BatteryModule) formatBattery() string {
	var builder strings.Builder

	if m.showIcon {
		icon := m.getBatteryIcon()
		builder.WriteString(icon)
		if m.showPercentage {
			builder.WriteString(" ")
		}
	}

	if m.showPercentage {
		builder.WriteString(fmt.Sprintf("%d%%", m.percentage))
	}

	return builder.String()
}

// getBatteryIcon returns battery icon based on status
func (m *BatteryModule) getBatteryIcon() string {
	if m.isCharging {
		return ""
	}

	if m.percentage >= 75 {
		return ""
	} else if m.percentage >= 50 {
		return ""
	} else if m.percentage >= 25 {
		return ""
	} else {
		return ""
	}
}

// GetPercentage returns current battery percentage
func (m *BatteryModule) GetPercentage() int {
	return m.percentage
}

// IsCharging returns whether battery is charging
func (m *BatteryModule) IsCharging() bool {
	return m.isCharging
}

// Cleanup cleans up resources
func (m *BatteryModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// BatteryModuleFactory is a factory for creating BatteryModule instances
type BatteryModuleFactory struct{}

// CreateModule creates a new BatteryModule instance
func (f *BatteryModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewBatteryModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *BatteryModuleFactory) ModuleName() string {
	return "battery"
}

// DefaultConfig returns default configuration
func (f *BatteryModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"battery_path":    "/sys/class/power_supply/BAT0/capacity",
		"show_percentage": true,
		"show_icon":       true,
		"interval":        "30s",
		"css_classes":     []string{"battery-module"},
	}
}

// Dependencies returns module dependencies
func (f *BatteryModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &BatteryModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
