package launcher

import (
	"context"
	"os/exec"
	"strconv"
	"strings"

	"github.com/chess10kp/locus/internal/config"
)

type BluetoothDevice struct {
	MAC       string
	Name      string
	Connected bool
}

type BluetoothLauncher struct {
	config  *config.Config
	devices []BluetoothDevice
}

type BluetoothLauncherFactory struct{}

func (f *BluetoothLauncherFactory) Name() string {
	return "bluetooth"
}

func (f *BluetoothLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewBluetoothLauncher(cfg)
}

func init() {
	RegisterLauncherFactory(&BluetoothLauncherFactory{})
}

func NewBluetoothLauncher(cfg *config.Config) *BluetoothLauncher {
	return &BluetoothLauncher{
		config:  cfg,
		devices: []BluetoothDevice{},
	}
}

func (l *BluetoothLauncher) Name() string {
	return "bluetooth"
}

func (l *BluetoothLauncher) CommandTriggers() []string {
	return []string{"bluetooth", "bt"}
}

func (l *BluetoothLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *BluetoothLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *BluetoothLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	l.scanDevices()

	q := strings.TrimSpace(strings.ToLower(query))

	if q == "" {
		items := l.GetPowerItems()
		items = append(items, l.GetAllDeviceItems()...)
		return items
	}

	var items []*LauncherItem
	for _, device := range l.devices {
		if strings.Contains(strings.ToLower(device.Name), q) ||
			strings.Contains(strings.ToLower(device.MAC), q) {
			items = append(items, l.createDeviceItem(device))
		}
	}

	if len(items) == 0 {
		items = append(items, &LauncherItem{
			Title:      "Refresh Devices",
			Subtitle:   "Scan for bluetooth devices",
			Icon:       "bluetooth-symbolic",
			ActionData: NewShellAction("bluetoothctl scan on"),
			Launcher:   l,
		})
	}

	return items
}

func (l *BluetoothLauncher) GetPowerItems() []*LauncherItem {
	ctx, cancel := context.WithTimeout(context.Background(), 2000000000)
	defer cancel()

	isPowered := false
	cmd := exec.CommandContext(ctx, "bluetoothctl", "show")
	if output, err := cmd.Output(); err == nil {
		isPowered = strings.Contains(string(output), "Powered: yes")
	}

	if isPowered {
		return []*LauncherItem{
			{
				Title:      "Turn Off Bluetooth",
				Subtitle:   "Disable bluetooth adapter",
				Icon:       "bluetooth-disabled-symbolic",
				ActionData: NewShellAction("bluetoothctl power off"),
				Launcher:   l,
			},
		}
	}

	return []*LauncherItem{
		{
			Title:      "Turn On Bluetooth",
			Subtitle:   "Enable bluetooth adapter",
			Icon:       "bluetooth-symbolic",
			ActionData: NewShellAction("bluetoothctl power on"),
			Launcher:   l,
		},
	}
}

func (l *BluetoothLauncher) GetAllDeviceItems() []*LauncherItem {
	var items []*LauncherItem

	for _, device := range l.devices {
		items = append(items, l.createDeviceItem(device))
	}

	if len(items) == 0 {
		items = append(items, &LauncherItem{
			Title:    "No devices found",
			Subtitle: "Make sure Bluetooth is on and devices are paired",
			Icon:     "bluetooth-symbolic",
			Launcher: l,
		})
	}

	return items
}

func (l *BluetoothLauncher) createDeviceItem(device BluetoothDevice) *LauncherItem {
	var action string
	var subtitle string

	if device.Connected {
		action = "disconnect"
		subtitle = "Click to disconnect"
	} else {
		action = "connect"
		subtitle = "Click to connect"
	}

	icon := "bluetooth-symbolic"
	if device.Connected {
		icon = "bluetooth-active-symbolic"
	}

	return &LauncherItem{
		Title:      device.Name,
		Subtitle:   subtitle,
		Icon:       icon,
		ActionData: NewShellAction("bluetoothctl " + action + " " + device.MAC),
		Launcher:   l,
		Metadata: map[string]string{
			"mac":       device.MAC,
			"connected": strconv.FormatBool(device.Connected),
		},
	}
}

func (l *BluetoothLauncher) scanDevices() {
	ctx, cancel := context.WithTimeout(context.Background(), 5000000000)
	defer cancel()

	l.devices = []BluetoothDevice{}

	cmd := exec.CommandContext(ctx, "bluetoothctl", "devices")
	if output, err := cmd.Output(); err == nil {
		lines := strings.Split(string(output), "\n")
		for _, line := range lines {
			if strings.HasPrefix(line, "Device ") {
				parts := strings.Fields(line)
				if len(parts) >= 3 {
					mac := parts[1]
					name := strings.Join(parts[2:], " ")

					connected := false
					infoCmd := exec.CommandContext(ctx, "bluetoothctl", "info", mac)
					if infoOutput, err := infoCmd.Output(); err == nil {
						connected = strings.Contains(string(infoOutput), "Connected: yes")
					}

					l.devices = append(l.devices, BluetoothDevice{
						MAC:       mac,
						Name:      name,
						Connected: connected,
					})
				}
			}
		}
	}
}

func (l *BluetoothLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *BluetoothLauncher) Rebuild(ctx *LauncherContext) error {
	l.scanDevices()
	return nil
}

func (l *BluetoothLauncher) Cleanup() {
}

func (l *BluetoothLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}
