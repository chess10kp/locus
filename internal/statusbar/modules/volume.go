package modules

import (
	"fmt"
	"os/exec"
	"strconv"
	"strings"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// VolumeModule displays system volume status
type VolumeModule struct {
	*statusbar.BaseModule
	widget    *gtk.Label
	volumeCmd string
	muteCmd   string
	showIcon  bool
	volume    int
	isMuted   bool
}

// NewVolumeModule creates a new volume module
func NewVolumeModule() *VolumeModule {
	return &VolumeModule{
		BaseModule: statusbar.NewBaseModule("volume", statusbar.UpdateModePeriodic),
		widget:     nil,
		volumeCmd:  "pamixer --get-volume",
		muteCmd:    "pamixer --get-mute",
		showIcon:   true,
		volume:     50,
		isMuted:    false,
	}
}

// CreateWidget creates a volume label widget
func (m *VolumeModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.formatVolume())
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

// UpdateWidget updates volume widget
func (m *VolumeModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	m.readVolumeStatus()
	formatted := m.formatVolume()
	label.SetText(formatted)

	return nil
}

// Initialize initializes the module with configuration
func (m *VolumeModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if volumeCmd, ok := config["volume_cmd"].(string); ok {
		m.volumeCmd = volumeCmd
	}

	if muteCmd, ok := config["mute_cmd"].(string); ok {
		m.muteCmd = muteCmd
	}

	if showIcon, ok := config["show_icon"].(bool); ok {
		m.showIcon = showIcon
	}

	m.SetCSSClasses([]string{"volume-module"})

	m.readVolumeStatus()

	return nil
}

// readVolumeStatus reads volume status from system
func (m *VolumeModule) readVolumeStatus() {
	// Get volume
	if cmd := exec.Command("sh", "-c", m.volumeCmd); cmd != nil {
		if output, err := cmd.Output(); err == nil {
			if vol, err := strconv.Atoi(strings.TrimSpace(string(output))); err == nil {
				m.volume = vol
			}
		}
	}

	// Get mute status
	if cmd := exec.Command("sh", "-c", m.muteCmd); cmd != nil {
		if output, err := cmd.Output(); err == nil {
			muteStr := strings.TrimSpace(string(output))
			m.isMuted = muteStr == "true" || muteStr == "1"
		}
	}
}

// formatVolume formats volume status for display
func (m *VolumeModule) formatVolume() string {
	var builder strings.Builder

	if m.showIcon {
		icon := m.getVolumeIcon()
		if icon != "" {
			builder.WriteString(icon)
			builder.WriteString(" ")
		}
	}

	if m.isMuted {
		builder.WriteString("MUTE")
	} else {
		builder.WriteString(fmt.Sprintf("%d%%", m.volume))
	}

	return builder.String()
}

// getVolumeIcon returns volume icon based on level and mute status
func (m *VolumeModule) getVolumeIcon() string {
	if m.isMuted {
		return "🔇"
	}

	switch {
	case m.volume == 0:
		return "🔇"
	case m.volume < 33:
		return "🔈"
	case m.volume < 66:
		return "🔉"
	default:
		return "🔊"
	}
}

// GetVolume returns current volume level
func (m *VolumeModule) GetVolume() int {
	return m.volume
}

// IsMuted returns whether volume is muted
func (m *VolumeModule) IsMuted() bool {
	return m.isMuted
}

// Cleanup cleans up resources
func (m *VolumeModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// VolumeModuleFactory is a factory for creating VolumeModule instances
type VolumeModuleFactory struct{}

// CreateModule creates a new VolumeModule instance
func (f *VolumeModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewVolumeModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *VolumeModuleFactory) ModuleName() string {
	return "volume"
}

// DefaultConfig returns default configuration
func (f *VolumeModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"volume_cmd":  "pamixer --get-volume",
		"mute_cmd":    "pamixer --get-mute",
		"show_icon":   true,
		"interval":    "10s",
		"css_classes": []string{"volume-module"},
	}
}

// Dependencies returns module dependencies
func (f *VolumeModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &VolumeModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
