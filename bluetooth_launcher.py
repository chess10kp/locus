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


class BluetoothLauncher:
    def __init__(self, launcher):
        self.launcher = launcher

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
            button.connect("clicked", self.on_bluetooth_clicked, item)
            self.launcher.list_box.append(button)
        self.launcher.current_apps = []

    def on_bluetooth_clicked(self, button, item):
        if item.startswith("Power:"):
            bluetooth_toggle_power()
        elif item.startswith("Scan:"):
            bluetooth_toggle_scan()
        elif item.startswith("Pairable:"):
            bluetooth_toggle_pairable()
        elif item.startswith("Discoverable:"):
            bluetooth_toggle_discoverable()
        else:
            # Device item
            # Extract mac from (mac)
            match = re.search(r"\(([^)]+)\)", item)
            if match:
                mac = match.group(1)
                bluetooth_toggle_connection(mac)
        # Refresh the menu by re-populating
        self.launcher.selected_row = None
        self.launcher.populate_apps(">bluetooth")
