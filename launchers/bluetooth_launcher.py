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
from utils.launcher_utils import LauncherEnhancer


class BluetoothHook(LauncherHook):
    def __init__(self, launcher):
        self.launcher = launcher

    def on_select(self, launcher, item_data):
        """Handle button clicks for bluetooth controls and devices."""
        if not item_data:
            return False

        # Handle both string and dict input
        data_str = (
            item_data if isinstance(item_data, str) else str(item_data.get("", ""))
        )

        if data_str.startswith("Power:"):
            bluetooth_toggle_power()
            launcher.selected_row = None
            launcher.populate_apps(">bluetooth")
            return True
        elif data_str.startswith("Scan:"):
            bluetooth_toggle_scan()
            launcher.selected_row = None
            launcher.populate_apps(">bluetooth")
            return True
        elif data_str.startswith("Pairable:"):
            bluetooth_toggle_pairable()
            launcher.selected_row = None
            launcher.populate_apps(">bluetooth")
            return True
        elif data_str.startswith("Discoverable:"):
            bluetooth_toggle_discoverable()
            launcher.selected_row = None
            launcher.populate_apps(">bluetooth")
            return True
        else:
            # Device item - Extract mac from (mac)
            match = re.search(r"\(([^)]+)\)", data_str)
            if match:
                mac = match.group(1)
                bluetooth_toggle_connection(mac)
                launcher.selected_row = None
                launcher.populate_apps(">bluetooth")
                return True

        return False

    def on_enter(self, launcher, text):
        """Handle enter key for bluetooth operations."""
        # For now, no specific enter handling for bluetooth
        return False

    def on_tab(self, launcher, text):
        """Handle tab completion for bluetooth commands."""
        # Only handle bluetooth commands
        if not text.startswith(">bluetooth"):
            return None

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
    @classmethod
    def check_dependencies(cls) -> tuple[bool, str]:
        """Check if required dependencies are available.

        Returns:
            Tuple of (available, error_message)
        """
        from utils import check_bluetoothctl

        if not check_bluetoothctl():
            return False, "bluetoothctl not found"
        return True, ""

    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.hook = BluetoothHook(self)

        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, "hook_registry"):
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
            device_items.append(f"{name}: {status}")
        all_items = [
            power_status,
            scan_status,
            pairable_status,
            discoverable_status,
        ] + device_items
        index = 1
        for item in all_items:
            metadata = launcher_core.METADATA.get("bluetooth", "")
            launcher_core.add_launcher_result(
                item, metadata, index=index if index <= 9 else None
            )
            index += 1
            if index > 9:  # Stop showing hints after 9
                break
        launcher_core.current_apps = []
