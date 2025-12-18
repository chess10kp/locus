# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import re
from utils import (
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
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from typing import Optional, Tuple


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


class BluetoothLauncher(LauncherInterface):
    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.hook = BluetoothHook(self)

        # Register with launcher registry
        from core.launcher_registry import launcher_registry
        launcher_registry.register(self)

        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, 'hook_registry'):
            main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self):
        return ["bluetooth"]

    @property
    def name(self):
        return "bluetooth"

    def get_size_mode(self):
        return LauncherSizeMode.DEFAULT, None

    def populate(self, query, launcher_core):
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
            metadata = launcher_core.METADATA.get("bluetooth", "")
            button = launcher_core.create_button_with_metadata(item, metadata)
            launcher_core.list_box.append(button)
        launcher_core.current_apps = []
