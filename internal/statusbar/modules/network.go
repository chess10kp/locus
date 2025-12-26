package modules

import (
	"os/exec"
	"strings"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// NetworkModule displays overall network connectivity status
type NetworkModule struct {
	*statusbar.BaseModule
	widget       *gtk.Label
	command      string
	showIcon     bool
	showEthernet bool
	showVpn      bool
	hasEthernet  bool
	hasWifi      bool
	hasVpn       bool
}

// NewNetworkModule creates a new network module
func NewNetworkModule() *NetworkModule {
	return &NetworkModule{
		BaseModule:   statusbar.NewBaseModule("network", statusbar.UpdateModePeriodic),
		widget:       nil,
		command:      "nmcli -t -f TYPE con show --active",
		showIcon:     true,
		showEthernet: true,
		showVpn:      true,
		hasEthernet:  false,
		hasWifi:      false,
		hasVpn:       false,
	}
}

// CreateWidget creates a network label widget
func (m *NetworkModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.formatNetwork())
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

// UpdateWidget updates network widget
func (m *NetworkModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	m.readNetworkStatus()
	formatted := m.formatNetwork()
	label.SetText(formatted)

	return nil
}

// Initialize initializes the module with configuration
func (m *NetworkModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if command, ok := config["command"].(string); ok {
		m.command = command
	}

	if showIcon, ok := config["show_icon"].(bool); ok {
		m.showIcon = showIcon
	}

	if showEthernet, ok := config["show_ethernet"].(bool); ok {
		m.showEthernet = showEthernet
	}

	if showVpn, ok := config["show_vpn"].(bool); ok {
		m.showVpn = showVpn
	}

	m.SetCSSClasses([]string{"network-module"})

	m.readNetworkStatus()

	return nil
}

// readNetworkStatus reads network status from system
func (m *NetworkModule) readNetworkStatus() {
	cmd := exec.Command("sh", "-c", m.command)
	output, err := cmd.Output()
	if err != nil {
		m.hasEthernet = false
		m.hasWifi = false
		m.hasVpn = false
		return
	}

	lines := strings.Split(string(output), "\n")
	m.hasEthernet = false
	m.hasWifi = false
	m.hasVpn = false

	for _, line := range lines {
		line = strings.TrimSpace(line)
		switch line {
		case "802-11-wireless":
			m.hasWifi = true
		case "802-3-ethernet":
			m.hasEthernet = true
		case "vpn":
			m.hasVpn = true
		}
	}
}

// formatNetwork formats network status for display
func (m *NetworkModule) formatNetwork() string {
	var builder strings.Builder

	if m.showIcon {
		icon := m.getNetworkIcon()
		if icon != "" {
			builder.WriteString(icon)
			builder.WriteString(" ")
		}
	}

	var types []string
	if m.showEthernet && m.hasEthernet {
		types = append(types, "Ethernet")
	}
	if m.hasWifi {
		types = append(types, "WiFi")
	}
	if m.showVpn && m.hasVpn {
		types = append(types, "VPN")
	}

	if len(types) > 0 {
		builder.WriteString(strings.Join(types, " + "))
	} else {
		builder.WriteString("Offline")
	}

	return builder.String()
}

// getNetworkIcon returns network icon based on connection types
func (m *NetworkModule) getNetworkIcon() string {
	if !m.hasEthernet && !m.hasWifi && !m.hasVpn {
		return "🌐"
	}

	if m.hasVpn {
		return "🔒"
	}

	if m.hasEthernet {
		return "🔌"
	}

	if m.hasWifi {
		return "📶"
	}

	return "🌐"
}

// HasEthernet returns ethernet connection status
func (m *NetworkModule) HasEthernet() bool {
	return m.hasEthernet
}

// HasWifi returns WiFi connection status
func (m *NetworkModule) HasWifi() bool {
	return m.hasWifi
}

// HasVpn returns VPN connection status
func (m *NetworkModule) HasVpn() bool {
	return m.hasVpn
}

// Cleanup cleans up resources
func (m *NetworkModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// NetworkModuleFactory is a factory for creating NetworkModule instances
type NetworkModuleFactory struct{}

// CreateModule creates a new NetworkModule instance
func (f *NetworkModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewNetworkModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *NetworkModuleFactory) ModuleName() string {
	return "network"
}

// DefaultConfig returns default configuration
func (f *NetworkModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"command":       "nmcli -t -f TYPE con show --active",
		"show_icon":     true,
		"show_ethernet": true,
		"show_vpn":      true,
		"interval":      "20s",
		"css_classes":   []string{"network-module"},
	}
}

// Dependencies returns module dependencies
func (f *NetworkModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &NetworkModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
