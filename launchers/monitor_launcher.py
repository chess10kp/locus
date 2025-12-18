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
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from typing import Optional, Tuple


class MonitorHook(LauncherHook):
    def __init__(self, main_launcher=None):
        self.launcher = main_launcher

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


class MonitorLauncher(LauncherInterface):
    def __init__(self, main_launcher=None):
        if main_launcher:
            main_launcher.launcher_registry.register_launcher(self)
            self.hook = MonitorHook(main_launcher)
            main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self) -> list:
        return [">monitor"]

    @property
    def name(self) -> str:
        return "monitor"

    def get_size_mode(self) -> 'LauncherSizeMode':
        return LauncherSizeMode.COMPACT

    def populate(self, query: str, launcher_core) -> None:
        monitors = get_monitors()
        monitor_items = []
        for name, status in monitors:
            monitor_items.append(f"{name}: {status}")
        for item in monitor_items:
            metadata = launcher_core.METADATA.get("monitor", "")
            button = launcher_core.create_button_with_metadata(item, metadata)
            launcher_core.list_box.append(button)
        launcher_core.current_apps = []
