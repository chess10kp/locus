package modules

import (
	"fmt"
	"os/exec"
	"strconv"
	"strings"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// DiskModule displays disk usage for specified mount points
type DiskModule struct {
	*statusbar.BaseModule
	widget      *gtk.Label
	command     string
	showIcon    bool
	showDetails bool
	mounts      []string
	usages      map[string]float64
}

// NewDiskModule creates a new disk module
func NewDiskModule() *DiskModule {
	return &DiskModule{
		BaseModule:  statusbar.NewBaseModule("disk", statusbar.UpdateModePeriodic),
		widget:      nil,
		command:     "df -h",
		showIcon:    true,
		showDetails: true,
		mounts:      []string{"/", "/home"},
		usages:      make(map[string]float64),
	}
}

// CreateWidget creates a disk label widget
func (m *DiskModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.formatDisk())
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

// UpdateWidget updates disk widget
func (m *DiskModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	m.readDiskUsage()
	formatted := m.formatDisk()
	label.SetText(formatted)

	// Update CSS classes for color
	if ctx, err := label.ToWidget().GetStyleContext(); err == nil {
		ctx.RemoveClass("disk-warning")
		ctx.RemoveClass("disk-critical")
		maxUsage := 0.0
		for _, usage := range m.usages {
			if usage > maxUsage {
				maxUsage = usage
			}
		}
		if maxUsage >= 90 {
			ctx.AddClass("disk-critical")
		} else if maxUsage >= 75 {
			ctx.AddClass("disk-warning")
		}
	}

	return nil
}

// Initialize initializes the module with configuration
func (m *DiskModule) Initialize(config map[string]interface{}) error {
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

	if mounts, ok := config["mounts"].([]interface{}); ok {
		m.mounts = make([]string, len(mounts))
		for i, mount := range mounts {
			if str, ok := mount.(string); ok {
				m.mounts[i] = str
			}
		}
	}

	m.SetCSSClasses([]string{"disk-module"})

	m.readDiskUsage()

	return nil
}

// readDiskUsage reads disk usage from system
func (m *DiskModule) readDiskUsage() {
	cmd := exec.Command("sh", "-c", m.command)
	output, err := cmd.Output()
	if err != nil {
		return
	}

	lines := strings.Split(string(output), "\n")
	m.usages = make(map[string]float64)

	for _, line := range lines[1:] { // Skip header
		fields := strings.Fields(line)
		if len(fields) < 6 {
			continue
		}

		mount := fields[5]                             // Mount point
		usageStr := strings.TrimSuffix(fields[4], "%") // Remove %

		// Check if this mount is in our list
		for _, targetMount := range m.mounts {
			if mount == targetMount {
				if usage, err := strconv.ParseFloat(usageStr, 64); err == nil {
					m.usages[mount] = usage
				}
				break
			}
		}
	}
}

// formatDisk formats disk usage for display
func (m *DiskModule) formatDisk() string {
	var builder strings.Builder

	if m.showIcon {
		icon := m.getDiskIcon()
		if icon != "" {
			builder.WriteString(icon)
			builder.WriteString(" ")
		}
	}

	if m.showDetails {
		var parts []string
		for _, mount := range m.mounts {
			if usage, exists := m.usages[mount]; exists {
				parts = append(parts, fmt.Sprintf("%s:%.0f%%", mount, usage))
			}
		}
		if len(parts) > 0 {
			builder.WriteString(strings.Join(parts, " "))
		} else {
			builder.WriteString("N/A")
		}
	} else {
		// Show highest usage
		maxUsage := 0.0
		for _, usage := range m.usages {
			if usage > maxUsage {
				maxUsage = usage
			}
		}
		builder.WriteString(fmt.Sprintf("%.0f%%", maxUsage))
	}

	return builder.String()
}

// getDiskIcon returns disk icon based on highest usage
func (m *DiskModule) getDiskIcon() string {
	maxUsage := 0.0
	for _, usage := range m.usages {
		if usage > maxUsage {
			maxUsage = usage
		}
	}

	switch {
	case maxUsage >= 90:
		return "💥"
	case maxUsage >= 75:
		return "🔴"
	case maxUsage >= 50:
		return "🟡"
	default:
		return "💿"
	}
}

// GetUsages returns disk usages map
func (m *DiskModule) GetUsages() map[string]float64 {
	return m.usages
}

// Cleanup cleans up resources
func (m *DiskModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// DiskModuleFactory is a factory for creating DiskModule instances
type DiskModuleFactory struct{}

// CreateModule creates a new DiskModule instance
func (f *DiskModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewDiskModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *DiskModuleFactory) ModuleName() string {
	return "disk"
}

// DefaultConfig returns default configuration
func (f *DiskModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"command":      "df -h",
		"show_icon":    true,
		"show_details": true,
		"mounts":       []string{"/", "/home"},
		"interval":     "30s",
		"css_classes":  []string{"disk-module"},
	}
}

// Dependencies returns module dependencies
func (f *DiskModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &DiskModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
