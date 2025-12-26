package modules

import (
	"fmt"
	"os/exec"
	"strings"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// BluetoothDevice represents a bluetooth device
type BluetoothDevice struct {
	MAC       string
	Name      string
	Connected bool
}

// BluetoothModule displays bluetooth status with device menu
type BluetoothModule struct {
	*statusbar.BaseModule
	widget    *gtk.Button
	popover   *gtk.Popover
	devices   []BluetoothDevice
	isPowered bool
	showIcon  bool
}

// NewBluetoothModule creates a new bluetooth module
func NewBluetoothModule() *BluetoothModule {
	return &BluetoothModule{
		BaseModule: statusbar.NewBaseModule("bluetooth", statusbar.UpdateModePeriodic),
		widget:     nil,
		popover:    nil,
		devices:    []BluetoothDevice{},
		isPowered:  false,
		showIcon:   true,
	}
}

// CreateWidget creates a bluetooth button widget
func (m *BluetoothModule) CreateWidget() (gtk.IWidget, error) {
	button, err := gtk.ButtonNewWithLabel(m.formatBluetooth())
	if err != nil {
		return nil, err
	}

	button.SetRelief(gtk.RELIEF_NONE)
	m.widget = button

	// Create popover for device menu
	popover, err := gtk.PopoverNew(button)
	if err != nil {
		return nil, err
	}
	m.popover = popover

	// Create menu content
	menuBox, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 5)
	if err != nil {
		return nil, err
	}
	menuBox.SetMarginStart(10)
	menuBox.SetMarginEnd(10)
	menuBox.SetMarginTop(10)
	menuBox.SetMarginBottom(10)

	popover.Add(menuBox)
	m.updateDeviceMenu()

	helper := &statusbar.WidgetHelper{}
	if err := helper.ApplyStylesToWidget(button, m.GetStyles(), m.GetCSSClasses()); err != nil {
		return nil, err
	}

	button.Connect("clicked", func() {
		if m.popover != nil {
			m.updateDeviceMenu()
			m.popover.Popup()
		}
	})

	return button, nil
}

// UpdateWidget updates bluetooth widget
func (m *BluetoothModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	button, ok := widget.(*gtk.Button)
	if !ok {
		return nil
	}

	m.readBluetoothStatus()
	formatted := m.formatBluetooth()
	button.SetLabel(formatted)

	// Update CSS classes for color
	if ctx, err := button.ToWidget().GetStyleContext(); err == nil {
		ctx.RemoveClass("bluetooth-connected")
		for _, device := range m.devices {
			if device.Connected {
				ctx.AddClass("bluetooth-connected")
				break
			}
		}
	}

	return nil
}

// Initialize initializes the module with configuration
func (m *BluetoothModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if showIcon, ok := config["show_icon"].(bool); ok {
		m.showIcon = showIcon
	}

	m.SetCSSClasses([]string{"bluetooth-module", "bluetooth-button"})

	m.SetClickHandler(func(widget gtk.IWidget) bool {
		return true // Handled by GTK signal
	})

	m.readBluetoothStatus()

	return nil
}

// readBluetoothStatus reads bluetooth status from system
func (m *BluetoothModule) readBluetoothStatus() {
	// Check if powered on
	if cmd := exec.Command("bluetoothctl", "show"); cmd != nil {
		if output, err := cmd.Output(); err == nil {
			m.isPowered = strings.Contains(string(output), "Powered: yes")
		}
	}

	if !m.isPowered {
		m.devices = []BluetoothDevice{}
		return
	}

	// Get devices
	m.devices = []BluetoothDevice{}
	if cmd := exec.Command("bluetoothctl", "devices"); cmd != nil {
		if output, err := cmd.Output(); err == nil {
			lines := strings.Split(string(output), "\n")
			for _, line := range lines {
				if strings.HasPrefix(line, "Device ") {
					parts := strings.Fields(line)
					if len(parts) >= 3 {
						mac := parts[1]
						name := strings.Join(parts[2:], " ")

						// Check if connected
						connected := false
						if infoCmd := exec.Command("bluetoothctl", "info", mac); infoCmd != nil {
							if infoOutput, err := infoCmd.Output(); err == nil {
								connected = strings.Contains(string(infoOutput), "Connected: yes")
							}
						}

						m.devices = append(m.devices, BluetoothDevice{
							MAC:       mac,
							Name:      name,
							Connected: connected,
						})
					}
				}
			}
		}
	}
}

// formatBluetooth formats bluetooth status for display
func (m *BluetoothModule) formatBluetooth() string {
	var builder strings.Builder

	if m.showIcon {
		icon := m.getBluetoothIcon()
		if icon != "" {
			builder.WriteString(icon)
			builder.WriteString(" ")
		}
	}

	if !m.isPowered {
		builder.WriteString("off")
		return builder.String()
	}

	connectedCount := 0
	for _, device := range m.devices {
		if device.Connected {
			connectedCount++
		}
	}

	if len(m.devices) == 0 {
		builder.WriteString("no devices")
	} else {
		builder.WriteString(fmt.Sprintf("%d/%d", connectedCount, len(m.devices)))
	}

	return builder.String()
}

// getBluetoothIcon returns bluetooth icon based on status
func (m *BluetoothModule) getBluetoothIcon() string {
	if !m.isPowered {
		return "📶"
	}

	// Check if any device is connected
	for _, device := range m.devices {
		if device.Connected {
			return "🔵"
		}
	}

	return "📶"
}

// updateDeviceMenu updates the popover menu with current devices
func (m *BluetoothModule) updateDeviceMenu() {
	if m.popover == nil {
		return
	}

	// Clear existing menu
	children := m.popover.GetChildren()
	children.Foreach(func(item interface{}) {
		if widget, ok := item.(*gtk.Widget); ok {
			m.popover.Remove(widget)
		}
	})

	menuBox, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 5)
	if err != nil {
		return
	}
	menuBox.SetMarginStart(10)
	menuBox.SetMarginEnd(10)
	menuBox.SetMarginTop(10)
	menuBox.SetMarginBottom(10)

	// Power toggle
	powerLabel := "Turn Bluetooth Off"
	if !m.isPowered {
		powerLabel = "Turn Bluetooth On"
	}
	powerBtn, err := gtk.ButtonNewWithLabel(powerLabel)
	if err == nil {
		powerBtn.SetRelief(gtk.RELIEF_NONE)
		powerBtn.Connect("clicked", func() {
			m.toggleBluetoothPower()
			m.popover.Popdown()
		})
		menuBox.PackStart(powerBtn, false, false, 0)
	}

	if m.isPowered {
		// Separator
		sep, err := gtk.SeparatorNew(gtk.ORIENTATION_HORIZONTAL)
		if err == nil {
			menuBox.PackStart(sep, false, false, 5)
		}

		// Device list
		for _, device := range m.devices {
			deviceBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 5)
			if err != nil {
				continue
			}

			statusIcon := "○"
			if device.Connected {
				statusIcon = "●"
			}

			label, err := gtk.LabelNew(fmt.Sprintf("%s %s", statusIcon, device.Name))
			if err == nil {
				label.SetHAlign(gtk.ALIGN_START)
				label.SetHExpand(true)
				deviceBox.PackStart(label, true, true, 0)
			}

			actionBtn, err := gtk.ButtonNewWithLabel("Toggle")
			if err == nil {
				actionBtn.SetRelief(gtk.RELIEF_NONE)
				mac := device.MAC // Capture for closure
				actionBtn.Connect("clicked", func() {
					m.toggleDeviceConnection(mac)
					m.popover.Popdown()
				})
				deviceBox.PackStart(actionBtn, false, false, 0)
			}

			menuBox.PackStart(deviceBox, false, false, 0)
		}

		if len(m.devices) == 0 {
			noDevicesLabel, err := gtk.LabelNew("No devices paired")
			if err == nil {
				menuBox.PackStart(noDevicesLabel, false, false, 0)
			}
		}
	}

	m.popover.Add(menuBox)
	menuBox.ShowAll()
}

// toggleBluetoothPower toggles bluetooth power
func (m *BluetoothModule) toggleBluetoothPower() {
	var cmd *exec.Cmd
	if m.isPowered {
		cmd = exec.Command("bluetoothctl", "power", "off")
	} else {
		cmd = exec.Command("bluetoothctl", "power", "on")
	}
	cmd.Run()
	m.readBluetoothStatus()
	if m.widget != nil {
		m.widget.SetLabel(m.formatBluetooth())
	}
}

// toggleDeviceConnection toggles connection to a device
func (m *BluetoothModule) toggleDeviceConnection(mac string) {
	var cmd *exec.Cmd

	// Find device
	var device *BluetoothDevice
	for i := range m.devices {
		if m.devices[i].MAC == mac {
			device = &m.devices[i]
			break
		}
	}

	if device == nil {
		return
	}

	if device.Connected {
		cmd = exec.Command("bluetoothctl", "disconnect", mac)
	} else {
		cmd = exec.Command("bluetoothctl", "connect", mac)
	}
	cmd.Run()
	m.readBluetoothStatus()
	if m.widget != nil {
		m.widget.SetLabel(m.formatBluetooth())
	}
}

// IsPowered returns whether bluetooth is powered
func (m *BluetoothModule) IsPowered() bool {
	return m.isPowered
}

// GetDevices returns the list of devices
func (m *BluetoothModule) GetDevices() []BluetoothDevice {
	return m.devices
}

// Cleanup cleans up resources
func (m *BluetoothModule) Cleanup() error {
	if m.popover != nil {
		m.popover.Destroy()
	}
	return m.BaseModule.Cleanup()
}

// BluetoothModuleFactory is a factory for creating BluetoothModule instances
type BluetoothModuleFactory struct{}

// CreateModule creates a new BluetoothModule instance
func (f *BluetoothModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewBluetoothModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *BluetoothModuleFactory) ModuleName() string {
	return "bluetooth"
}

// DefaultConfig returns default configuration
func (f *BluetoothModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"show_icon":   true,
		"interval":    "30s",
		"css_classes": []string{"bluetooth-module", "bluetooth-button"},
	}
}

// Dependencies returns module dependencies
func (f *BluetoothModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &BluetoothModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
