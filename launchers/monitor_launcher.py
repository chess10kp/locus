# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from utils import get_monitors, toggle_monitor
from core.hooks import LauncherHook


class MonitorHook(LauncherHook):
    def __init__(self, launcher):
        self.launcher = launcher

    def on_select(self, launcher, item_data):
        """Handle button clicks for monitor toggling."""
        if not item_data:
            return False

        # Extract monitor name from "NAME: status"
        if ":" in item_data:
            name = item_data.split(":")[0].strip()
            toggle_monitor(name)
            # Refresh the menu by re-populating
            launcher.selected_row = None
            launcher.populate_apps(">monitor")
            return True

        return False

    def on_enter(self, launcher, text):
        """Handle enter key for monitor operations."""
        # For now, no specific enter handling for monitor
        return False

    def on_tab(self, launcher, text):
        """Handle tab completion for monitor names."""
        monitors = get_monitors()
        monitor_names = [f"{name}: {status}" for name, status in monitors]
        matching_monitors = [
            m for m in monitor_names if m.lower().startswith(text.lower())
        ]

        if matching_monitors:
            return matching_monitors[0]

        return None


class MonitorLauncher:
    def __init__(self, launcher):
        self.launcher = launcher
        self.hook = MonitorHook(launcher)
        launcher.hook_registry.register_hook(self.hook)

    def populate(self):
        monitors = get_monitors()
        monitor_items = []
        for name, status in monitors:
            monitor_items.append(f"{name}: {status}")
        for item in monitor_items:
            metadata = self.launcher.METADATA.get("monitor", "")
            button = self.launcher.create_button_with_metadata(item, metadata)
            self.launcher.list_box.append(button)
        self.launcher.current_apps = []
