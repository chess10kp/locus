package modules

import (
	"fmt"
	"os/exec"
	"strconv"
	"strings"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// CpuModule displays CPU usage percentage
type CpuModule struct {
	*statusbar.BaseModule
	widget    *gtk.Label
	command   string
	showIcon  bool
	usage     float64
	showCores bool
	coreCount int
}

// NewCpuModule creates a new CPU module
func NewCpuModule() *CpuModule {
	return &CpuModule{
		BaseModule: statusbar.NewBaseModule("cpu", statusbar.UpdateModePeriodic),
		widget:     nil,
		command:    "mpstat 1 1 | awk 'NR==4 {print 100 - $NF}'",
		showIcon:   true,
		usage:      0.0,
		showCores:  false,
		coreCount:  0,
	}
}

// CreateWidget creates a CPU label widget
func (m *CpuModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.formatCpu())
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

// UpdateWidget updates CPU widget
func (m *CpuModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	m.readCpuUsage()
	formatted := m.formatCpu()
	label.SetText(formatted)

	return nil
}

// Initialize initializes the module with configuration
func (m *CpuModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if command, ok := config["command"].(string); ok {
		m.command = command
	}

	if showIcon, ok := config["show_icon"].(bool); ok {
		m.showIcon = showIcon
	}

	if showCores, ok := config["show_cores"].(bool); ok {
		m.showCores = showCores
		if showCores {
			m.coreCount = m.getCpuCoreCount()
		}
	}

	m.SetCSSClasses([]string{"cpu-module"})

	m.readCpuUsage()

	return nil
}

// readCpuUsage reads CPU usage from system
func (m *CpuModule) readCpuUsage() {
	cmd := exec.Command("sh", "-c", m.command)
	output, err := cmd.Output()
	if err != nil {
		m.usage = 0.0
		return
	}

	usageStr := strings.TrimSpace(string(output))
	usage, err := strconv.ParseFloat(usageStr, 64)
	if err != nil {
		m.usage = 0.0
		return
	}

	m.usage = usage
}

// getCpuCoreCount gets the number of CPU cores
func (m *CpuModule) getCpuCoreCount() int {
	cmd := exec.Command("nproc")
	output, err := cmd.Output()
	if err != nil {
		return 0
	}

	countStr := strings.TrimSpace(string(output))
	count, err := strconv.Atoi(countStr)
	if err != nil {
		return 0
	}

	return count
}

// formatCpu formats CPU usage for display
func (m *CpuModule) formatCpu() string {
	var builder strings.Builder

	if m.showIcon {
		icon := m.getCpuIcon()
		if icon != "" {
			builder.WriteString(icon)
			builder.WriteString(" ")
		}
	}

	builder.WriteString(fmt.Sprintf("%.0f%%", m.usage))

	if m.showCores && m.coreCount > 0 {
		builder.WriteString(fmt.Sprintf(" (%d cores)", m.coreCount))
	}

	return builder.String()
}

// getCpuIcon returns CPU icon based on usage
func (m *CpuModule) getCpuIcon() string {
	switch {
	case m.usage >= 80:
		return "🔥"
	case m.usage >= 50:
		return "⚡"
	case m.usage >= 20:
		return "💻"
	default:
		return "❄️"
	}
}

// GetUsage returns current CPU usage
func (m *CpuModule) GetUsage() float64 {
	return m.usage
}

// Cleanup cleans up resources
func (m *CpuModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// CpuModuleFactory is a factory for creating CpuModule instances
type CpuModuleFactory struct{}

// CreateModule creates a new CpuModule instance
func (f *CpuModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewCpuModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *CpuModuleFactory) ModuleName() string {
	return "cpu"
}

// DefaultConfig returns default configuration
func (f *CpuModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"command":     "mpstat 1 1 | awk 'NR==4 {print 100 - $NF}'",
		"show_icon":   true,
		"show_cores":  false,
		"interval":    "10s",
		"css_classes": []string{"cpu-module"},
	}
}

// Dependencies returns module dependencies
func (f *CpuModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &CpuModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
