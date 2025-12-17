# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from monitor import get_monitors, toggle_monitor


class MonitorLauncher:
    def __init__(self, launcher):
        self.launcher = launcher

    def populate(self):
        monitors = get_monitors()
        monitor_items = []
        for name, status in monitors:
            monitor_items.append(f"{name}: {status}")
        for item in monitor_items:
            metadata = self.launcher.METADATA.get("monitor", "")
            button = self.launcher.create_button_with_metadata(item, metadata)
            button.connect("clicked", self.on_monitor_clicked, item)
            self.launcher.list_box.append(button)
        self.launcher.current_apps = []

    def on_monitor_clicked(self, button, item):
        # Extract monitor name from "NAME: status"
        name = item.split(":")[0].strip()
        toggle_monitor(name)
        # Refresh the menu by re-populating
        self.launcher.selected_row = None
        self.launcher.populate_apps(">monitor")
