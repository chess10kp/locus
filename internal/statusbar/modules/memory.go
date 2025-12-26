package modules

import (
	"fmt"
	"os/exec"
	"strconv"
	"strings"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// MemoryModule displays memory usage
type MemoryModule struct {
	*statusbar.BaseModule
	widget      *gtk.Label
	command     string
	showIcon    bool
	showDetails bool
	used        float64
	total       float64
	percentage  float64
}

// NewMemoryModule creates a new memory module
func NewMemoryModule() *MemoryModule {
	return &MemoryModule{
		BaseModule:  statusbar.NewBaseModule("memory", statusbar.UpdateModePeriodic),
		widget:      nil,
		command:     "free -h | awk 'NR==2{print $3 \"/\" $2}'",
		showIcon:    true,
		showDetails: true,
		used:        0.0,
		total:       0.0,
		percentage:  0.0,
	}
}

// CreateWidget creates a memory label widget
func (m *MemoryModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.formatMemory())
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

// UpdateWidget updates memory widget
func (m *MemoryModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	m.readMemoryUsage()
	formatted := m.formatMemory()
	label.SetText(formatted)

	return nil
}

// Initialize initializes the module with configuration
func (m *MemoryModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if command, ok := config["command"].(string); ok {
		m.command = command
	}

	if showIcon, ok := config["show_icon"].(bool); ok {
		m.showIcon = showIcon
	}

	if showDetails, ok := config["show_details"].(bool); ok {
		m.showDetails = showDetails
	}

	m.SetCSSClasses([]string{"memory-module"})

	m.readMemoryUsage()

	return nil
}

// readMemoryUsage reads memory usage from system
func (m *MemoryModule) readMemoryUsage() {
	// Get detailed usage
	cmd := exec.Command("free", "-b") // bytes for accurate calculation
	output, err := cmd.Output()
	if err != nil {
		m.used = 0.0
		m.total = 0.0
		m.percentage = 0.0
		return
	}

	lines := strings.Split(string(output), "\n")
	if len(lines) < 2 {
		return
	}

	fields := strings.Fields(lines[1]) // Mem line
	if len(fields) < 7 {
		return
	}

	totalBytes, _ := strconv.ParseFloat(fields[1], 64)
	usedBytes, _ := strconv.ParseFloat(fields[2], 64)

	m.total = totalBytes / (1024 * 1024 * 1024) // GB
	m.used = usedBytes / (1024 * 1024 * 1024)   // GB
	if m.total > 0 {
		m.percentage = (m.used / m.total) * 100
	}
}

// formatMemory formats memory usage for display
func (m *MemoryModule) formatMemory() string {
	var builder strings.Builder

	if m.showIcon {
		icon := m.getMemoryIcon()
		if icon != "" {
			builder.WriteString(icon)
			builder.WriteString(" ")
		}
	}

	if m.showDetails {
		builder.WriteString(fmt.Sprintf("%.1f/%.1fGB (%.0f%%)", m.used, m.total, m.percentage))
	} else {
		builder.WriteString(fmt.Sprintf("%.0f%%", m.percentage))
	}

	return builder.String()
}

// getMemoryIcon returns memory icon based on usage
func (m *MemoryModule) getMemoryIcon() string {
	switch {
	case m.percentage >= 90:
		return "💥"
	case m.percentage >= 75:
		return "🔴"
	case m.percentage >= 50:
		return "🟡"
	default:
		return "💾"
	}
}

// GetUsed returns used memory in GB
func (m *MemoryModule) GetUsed() float64 {
	return m.used
}

// GetTotal returns total memory in GB
func (m *MemoryModule) GetTotal() float64 {
	return m.total
}

// GetPercentage returns memory usage percentage
func (m *MemoryModule) GetPercentage() float64 {
	return m.percentage
}

// Cleanup cleans up resources
func (m *MemoryModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// MemoryModuleFactory is a factory for creating MemoryModule instances
type MemoryModuleFactory struct{}

// CreateModule creates a new MemoryModule instance
func (f *MemoryModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewMemoryModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *MemoryModuleFactory) ModuleName() string {
	return "memory"
}

// DefaultConfig returns default configuration
func (f *MemoryModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"command":      "free -b",
		"show_icon":    true,
		"show_details": true,
		"interval":     "10s",
		"css_classes":  []string{"memory-module"},
	}
}

// Dependencies returns module dependencies
func (f *MemoryModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &MemoryModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
