package modules

import (
	"fmt"
	"os/exec"
	"strconv"
	"strings"

	"github.com/chess10kp/locus/internal/statusbar"
	"github.com/gotk3/gotk3/gtk"
)

// BrightnessModule displays screen brightness level
type BrightnessModule struct {
	*statusbar.BaseModule
	widget     *gtk.Label
	command    string
	device     string
	showIcon   bool
	current    int
	maximum    int
	percentage float64
}

// NewBrightnessModule creates a new brightness module
func NewBrightnessModule() *BrightnessModule {
	return &BrightnessModule{
		BaseModule: statusbar.NewBaseModule("brightness", statusbar.UpdateModePeriodic),
		widget:     nil,
		command:    "brightnessctl -m",
		device:     "",
		showIcon:   true,
		current:    0,
		maximum:    0,
		percentage: 0.0,
	}
}

// CreateWidget creates a brightness label widget
func (m *BrightnessModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.formatBrightness())
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

// UpdateWidget updates brightness widget
func (m *BrightnessModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	m.readBrightness()
	formatted := m.formatBrightness()
	label.SetText(formatted)

	// Update CSS classes for color
	if ctx, err := label.ToWidget().GetStyleContext(); err == nil {
		ctx.RemoveClass("brightness-night")
		if m.percentage < 50 {
			ctx.AddClass("brightness-night")
		}
	}

	return nil
}

// Initialize initializes the module with configuration
func (m *BrightnessModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if command, ok := config["command"].(string); ok {
		m.command = command
	}

	if device, ok := config["device"].(string); ok {
		m.device = device
		if device != "" {
			m.command = fmt.Sprintf("brightnessctl -d %s -m", device)
		}
	}

	if showIcon, ok := config["show_icon"].(bool); ok {
		m.showIcon = showIcon
	}

	m.SetCSSClasses([]string{"brightness-module"})

	m.readBrightness()

	return nil
}

// readBrightness reads brightness from system
func (m *BrightnessModule) readBrightness() {
	cmd := exec.Command("sh", "-c", m.command)
	output, err := cmd.Output()
	if err != nil {
		m.current = 0
		m.maximum = 0
		m.percentage = 0.0
		return
	}

	// brightnessctl -m output format: device,class,current,percent,max
	fields := strings.Split(strings.TrimSpace(string(output)), ",")
	if len(fields) >= 5 {
		if current, err := strconv.Atoi(fields[2]); err == nil {
			m.current = current
		}
		if max, err := strconv.Atoi(fields[4]); err == nil {
			m.maximum = max
		}
		if percentStr := strings.TrimSuffix(fields[3], "%"); true {
			if percent, err := strconv.ParseFloat(percentStr, 64); err == nil {
				m.percentage = percent
			}
		}
	}
}

// formatBrightness formats brightness for display
func (m *BrightnessModule) formatBrightness() string {
	var builder strings.Builder

	if m.showIcon {
		icon := m.getBrightnessIcon()
		if icon != "" {
			builder.WriteString(icon)
			builder.WriteString(" ")
		}
	}

	builder.WriteString(fmt.Sprintf("%.0f%%", m.percentage))

	return builder.String()
}

// getBrightnessIcon returns brightness icon based on level
func (m *BrightnessModule) getBrightnessIcon() string {
	if m.percentage >= 50 {
		return "☀️"
	}
	return "🌙"
}

// GetCurrent returns current brightness value
func (m *BrightnessModule) GetCurrent() int {
	return m.current
}

// GetMaximum returns maximum brightness value
func (m *BrightnessModule) GetMaximum() int {
	return m.maximum
}

// GetPercentage returns brightness percentage
func (m *BrightnessModule) GetPercentage() float64 {
	return m.percentage
}

// Cleanup cleans up resources
func (m *BrightnessModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// BrightnessModuleFactory is a factory for creating BrightnessModule instances
type BrightnessModuleFactory struct{}

// CreateModule creates a new BrightnessModule instance
func (f *BrightnessModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewBrightnessModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *BrightnessModuleFactory) ModuleName() string {
	return "brightness"
}

// DefaultConfig returns default configuration
func (f *BrightnessModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"command":     "brightnessctl -m",
		"device":      "",
		"show_icon":   true,
		"interval":    "5s",
		"css_classes": []string{"brightness-module"},
	}
}

// Dependencies returns module dependencies
func (f *BrightnessModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &BrightnessModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
