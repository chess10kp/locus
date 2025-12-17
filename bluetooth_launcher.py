# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import re
from bluetooth import (
    bluetooth_power_on,
    bluetooth_scan_on,
    bluetooth_pairable_on,
    bluetooth_discoverable_on,
    bluetooth_get_devices,
    bluetooth_device_connected,
    bluetooth_toggle_power,
    bluetooth_toggle_scan,
    bluetooth_toggle_pairable,
    bluetooth_toggle_discoverable,
    bluetooth_toggle_connection,
)
from hooks import LauncherHook


class BluetoothHook(LauncherHook):
    def __init__(self, launcher):
        self.launcher = launcher

    def on_select(self, launcher, item_data):
        """Handle button clicks for bluetooth controls and devices."""
        if not item_data:
            return False

        if item_data.startswith("Power:"):
            bluetooth_toggle_power()
        elif item_data.startswith("Scan:"):
            bluetooth_toggle_scan()
        elif item_data.startswith("Pairable:"):
            bluetooth_toggle_pairable()
        elif item_data.startswith("Discoverable:"):
            bluetooth_toggle_discoverable()
        else:
            # Device item - Extract mac from (mac)
            match = re.search(r"\(([^)]+)\)", item_data)
            if match:
                mac = match.group(1)
                bluetooth_toggle_connection(mac)

        # Refresh the menu by re-populating
        launcher.selected_row = None
        launcher.populate_apps(">bluetooth")
        return True

    def on_enter(self, launcher, text):
        """Handle enter key for bluetooth operations."""
        # For now, no specific enter handling for bluetooth
        return False

    def on_tab(self, launcher, text):
        """Handle tab completion for bluetooth commands."""
        # Get current status items and devices for completion
        power_status = "Power: on" if bluetooth_power_on() else "Power: off"
        scan_status = "Scan: on" if bluetooth_scan_on() else "Scan: off"
        pairable_status = "Pairable: on" if bluetooth_pairable_on() else "Pairable: off"
        discoverable_status = (
            "Discoverable: on" if bluetooth_discoverable_on() else "Discoverable: off"
        )

        status_items = [power_status, scan_status, pairable_status, discoverable_status]

        # Add device names for completion
        devices = bluetooth_get_devices()
        device_names = [name for mac, name in devices]

        all_items = status_items + device_names
        matching_items = [
            item for item in all_items if item.lower().startswith(text.lower())
        ]

        if matching_items:
            return matching_items[0]

        return None


class BluetoothLauncher:
    def __init__(self, launcher):
        self.launcher = launcher
        self.hook = BluetoothHook(launcher)
        launcher.hook_registry.register_hook(self.hook)

    def populate(self):
        power_status = "Power: on" if bluetooth_power_on() else "Power: off"
        scan_status = "Scan: on" if bluetooth_scan_on() else "Scan: off"
        pairable_status = "Pairable: on" if bluetooth_pairable_on() else "Pairable: off"
        discoverable_status = (
            "Discoverable: on" if bluetooth_discoverable_on() else "Discoverable: off"
        )
        devices = bluetooth_get_devices()
        device_items = []
        for mac, name in devices:
            status = "Connected" if bluetooth_device_connected(mac) else "Disconnected"
            device_items.append(f"{name}: {status} ({mac})")
        all_items = [
            power_status,
            scan_status,
            pairable_status,
            discoverable_status,
        ] + device_items
        for item in all_items:
            metadata = self.launcher.METADATA.get("bluetooth", "")
            button = self.launcher.create_button_with_metadata(item, metadata)
            self.launcher.list_box.append(button)
        self.launcher.current_apps = []
