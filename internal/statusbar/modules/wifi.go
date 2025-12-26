package modules

import (
	"os/exec"
	"strconv"
	"strings"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// WifiModule displays WiFi connection status
type WifiModule struct {
	*statusbar.BaseModule
	widget        *gtk.Label
	command       string
	interfaceName string
	showIcon      bool
	showSignal    bool
	ssid          string
	signal        int
	isConnected   bool
}

// NewWifiModule creates a new WiFi module
func NewWifiModule() *WifiModule {
	return &WifiModule{
		BaseModule:    statusbar.NewBaseModule("wifi", statusbar.UpdateModePeriodic),
		widget:        nil,
		command:       "nmcli -t -f active,ssid,signal dev wifi",
		interfaceName: "wlan0",
		showIcon:      true,
		showSignal:    true,
		ssid:          "",
		signal:        0,
		isConnected:   false,
	}
}

// CreateWidget creates a WiFi label widget
func (m *WifiModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.formatWifi())
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

// UpdateWidget updates WiFi widget
func (m *WifiModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	m.readWifiStatus()
	formatted := m.formatWifi()
	label.SetText(formatted)

	return nil
}

// Initialize initializes the module with configuration
func (m *WifiModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if command, ok := config["command"].(string); ok {
		m.command = command
	}

	if interfaceName, ok := config["interface"].(string); ok {
		m.interfaceName = interfaceName
	}

	if showIcon, ok := config["show_icon"].(bool); ok {
		m.showIcon = showIcon
	}

	if showSignal, ok := config["show_signal"].(bool); ok {
		m.showSignal = showSignal
	}

	m.SetCSSClasses([]string{"wifi-module"})

	m.readWifiStatus()

	return nil
}

// readWifiStatus reads WiFi status from system
func (m *WifiModule) readWifiStatus() {
	cmd := exec.Command("sh", "-c", m.command)
	output, err := cmd.Output()
	if err != nil {
		m.isConnected = false
		m.ssid = ""
		m.signal = 0
		return
	}

	lines := strings.Split(string(output), "\n")
	m.isConnected = false
	m.ssid = ""
	m.signal = 0

	for _, line := range lines {
		if strings.TrimSpace(line) == "" {
			continue
		}

		parts := strings.Split(line, ":")
		if len(parts) >= 3 {
			active := parts[0]
			ssid := parts[1]
			signalStr := parts[2]

			if active == "yes" && ssid != "" {
				m.isConnected = true
				m.ssid = ssid
				if signal, err := strconv.Atoi(signalStr); err == nil {
					m.signal = signal
				}
				break // Use first active connection
			}
		}
	}
}

// formatWifi formats WiFi status for display
func (m *WifiModule) formatWifi() string {
	var builder strings.Builder

	if m.showIcon {
		icon := m.getWifiIcon()
		if icon != "" {
			builder.WriteString(icon)
			builder.WriteString(" ")
		}
	}

	if !m.isConnected {
		builder.WriteString("Disconnected")
		return builder.String()
	}

	builder.WriteString(m.ssid)

	if m.showSignal {
		signalBars := m.getSignalBars()
		if signalBars != "" {
			builder.WriteString(" (")
			builder.WriteString(signalBars)
			builder.WriteString(")")
		}
	}

	return builder.String()
}

// getWifiIcon returns WiFi icon based on connection status
func (m *WifiModule) getWifiIcon() string {
	if !m.isConnected {
		return "📶"
	}

	switch {
	case m.signal >= 75:
		return "📶"
	case m.signal >= 50:
		return "📶"
	case m.signal >= 25:
		return "📶"
	default:
		return "📶"
	}
}

// getSignalBars returns signal strength bars
func (m *WifiModule) getSignalBars() string {
	if m.signal >= 80 {
		return "●●●●"
	} else if m.signal >= 60 {
		return "●●●○"
	} else if m.signal >= 40 {
		return "●●○○"
	} else if m.signal >= 20 {
		return "●○○○"
	} else {
		return "○○○○"
	}
}

// GetSSID returns current SSID
func (m *WifiModule) GetSSID() string {
	return m.ssid
}

// GetSignal returns current signal strength
func (m *WifiModule) GetSignal() int {
	return m.signal
}

// IsConnected returns connection status
func (m *WifiModule) IsConnected() bool {
	return m.isConnected
}

// Cleanup cleans up resources
func (m *WifiModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// WifiModuleFactory is a factory for creating WifiModule instances
type WifiModuleFactory struct{}

// CreateModule creates a new WifiModule instance
func (f *WifiModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewWifiModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *WifiModuleFactory) ModuleName() string {
	return "wifi"
}

// DefaultConfig returns default configuration
func (f *WifiModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"command":     "nmcli -t -f active,ssid,signal dev wifi",
		"interface":   "wlan0",
		"show_icon":   true,
		"show_signal": true,
		"interval":    "15s",
		"css_classes": []string{"wifi-module"},
	}
}

// Dependencies returns module dependencies
func (f *WifiModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &WifiModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
