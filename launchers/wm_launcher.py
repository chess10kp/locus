# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import subprocess
from typing import Any, Optional
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode


class WMHook(LauncherHook):
    def __init__(self, wm_launcher):
        self.wm_launcher = wm_launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """Handle window manager command execution"""
        if isinstance(item_data, str) and item_data.startswith("wm:"):
            command = item_data[3:]  # Remove "wm:" prefix
            self.wm_launcher.execute_wm_command(command)
            launcher.hide()
            return True
        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle window manager enter key"""
        if text.startswith(">wm "):
            command = text[4:].strip()
            self.wm_launcher.execute_wm_command(command)
            launcher.hide()
            return True
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle window manager tab completion"""
        if text.startswith(">wm"):
            return ">wm "
        return None


class WMLauncher(LauncherInterface):
    @classmethod
    def check_dependencies(cls) -> tuple[bool, str]:
        """Check if required dependencies are available.

        Returns:
            Tuple of (available, error_message)
        """
        try:
            # Try scrollmsg first, then swaymsg as fallback
            result = subprocess.run(
                ["scrollmsg", "--version"], capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                return True, ""
        except (subprocess.TimeoutExpired, FileNotFoundError):
            try:
                result = subprocess.run(
                    ["swaymsg", "--version"], capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    return True, ""
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return (
                    False,
                    "Neither scrollmsg nor swaymsg found - is scrollwm or sway installed?",
                )
        return False, "Window manager command failed"

    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.hook = WMHook(self)
        self.use_scroll = True  # Default to scroll, will check in execute

        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, "hook_registry"):
            main_launcher.hook_registry.register_hook(self.hook)

        self.commands = {
            # Window Management
            "toggle floating": "floating toggle",
            "toggle fullscreen": "fullscreen toggle",
            "toggle maximize": "maximize toggle",
            "toggle pin": "pin toggle",
            "center window": "move position center",
            "close window": "kill",
            "focus left": "focus left",
            "focus right": "focus right",
            "focus up": "focus up",
            "focus down": "focus down",
            "move left": "move left",
            "move right": "move right",
            "move up": "move up",
            "move down": "move down",
            "swap left": "swap left",
            "swap right": "swap right",
            "swap up": "swap up",
            "swap down": "swap down",
            # Workspace Navigation
            "workspace 1": "workspace number 1",
            "workspace 2": "workspace number 2",
            "workspace 3": "workspace number 3",
            "workspace 4": "workspace number 4",
            "workspace 5": "workspace number 5",
            "workspace 6": "workspace number 6",
            "workspace 7": "workspace number 7",
            "workspace 8": "workspace number 8",
            "workspace 9": "workspace number 9",
            "workspace 10": "workspace number 10",
            "next workspace": "workspace next",
            "previous workspace": "workspace prev",
            "move to workspace 1": "move container to workspace number 1",
            "move to workspace 2": "move container to workspace number 2",
            "move to workspace 3": "move container to workspace number 3",
            "move to workspace 4": "move container to workspace number 4",
            "move to workspace 5": "move container to workspace number 5",
            "move to workspace 6": "move container to workspace number 6",
            "move to workspace 7": "move container to workspace number 7",
            "move to workspace 8": "move container to workspace number 8",
            "move to workspace 9": "move container to workspace number 9",
            "move to workspace 10": "move container to workspace number 10",
            "move to 1 silent": "move container to workspace number 1, workspace number 1",
            "move to 2 silent": "move container to workspace number 2, workspace number 2",
            "move to 3 silent": "move container to workspace number 3, workspace number 3",
            "move to 4 silent": "move container to workspace number 4, workspace number 4",
            "move to 5 silent": "move container to workspace number 5, workspace number 5",
            "move to 6 silent": "move container to workspace number 6, workspace number 6",
            "move to 7 silent": "move container to workspace number 7, workspace number 7",
            "move to 8 silent": "move container to workspace number 8, workspace number 8",
            "move to 9 silent": "move container to workspace number 9, workspace number 9",
            "move to 10 silent": "move container to workspace number 10, workspace number 10",
            "scratchpad": "move scratchpad",
            "empty workspace": "workspace back_and_forth",
            # Window Groups (Tabs)
            "create group": "layout tabbed",
            "join group left": "focus left, layout tabbed",
            "join group right": "focus right, layout tabbed",
            "remove from group": "layout splith",
            "next in group": "focus right",
            "prev in group": "focus left",
            # Scroll-specific commands
            "toggle overview": "overview toggle",
            "enable animations": "animations_enable",
            "disable animations": "animations_disable",
            "reset alignment": "align reset",
            "jump mode": "jump",
            "cycle size": "cycle_size",
            "set size small": "set_size small",
            "set size medium": "set_size medium",
            "set size large": "set_size large",
            "fit size": "fit_size",
        }

    @property
    def command_triggers(self):
        return ["wm"]

    @property
    def name(self):
        return "wm"

    def get_size_mode(self):
        return LauncherSizeMode.DEFAULT, None

    def handles_enter(self):
        return True

    def handle_enter(self, query: str, launcher_core) -> bool:
        if query:
            self.execute_wm_command(query)
            launcher_core.hide()
            return True
        return False

    def populate(self, query, launcher_core):
        """Populate window manager commands based on query"""
        index = 1

        # Filter commands by query if provided
        filtered_commands = {}
        if query:
            query_lower = query.lower()
            for display_name, wm_command in self.commands.items():
                if query_lower in display_name.lower():
                    filtered_commands[display_name] = wm_command
        else:
            filtered_commands = self.commands

        # Display matching commands
        for display_name, wm_command in sorted(filtered_commands.items()):
            launcher_core.add_launcher_result(
                display_name,
                f"Execute: {wm_command}",
                index=index,
                action_data=f"wm:{wm_command}",
            )
            index += 1

        # If no matches and query provided, show as custom command
        if query and not filtered_commands:
            launcher_core.add_launcher_result(
                f"Execute: {query}",
                "Run custom window manager command",
                index=1,
                action_data=f"wm:{query}",
            )
        elif not query:
            launcher_core.add_launcher_result(
                "Usage: >wm <command>",
                "Enter window manager command or select from list",
                index=1,
            )

        launcher_core.current_apps = []

    def execute_wm_command(self, command: str) -> bool:
        """Execute a window manager command."""
        try:
            # Determine which command to use (scrollmsg or swaymsg)
            wm_command = "scrollmsg"
            try:
                # Test if scrollmsg is available
                result = subprocess.run(
                    ["scrollmsg", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                if result.returncode != 0:
                    wm_command = "swaymsg"
            except (subprocess.TimeoutExpired, FileNotFoundError):
                wm_command = "swaymsg"

            # Execute window manager command
            result = subprocess.run(
                [wm_command, command], capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                print(f"Window manager command executed: {command}")
                return True
            else:
                print(f"Window manager command failed: {result.stderr}")
                return False

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"Error executing window manager command: {e}")
            return False
