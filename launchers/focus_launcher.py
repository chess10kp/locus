# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import subprocess
import os
import shlex
from gi.repository import GLib
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from typing import Any, Optional, List, Union
from utils import send_status_message
from utils.launcher_utils import LauncherEnhancer
from datetime import datetime, timedelta


class FocusHook(LauncherHook):
    def __init__(self, focus_launcher):
        self.focus_launcher = focus_launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """Handle focus button clicks"""
        if isinstance(item_data, str) and item_data.startswith("focus:"):
            action = item_data[6:]  # Remove "focus:" prefix
            if action == "start":
                self.focus_launcher.start_focus_session()
            elif action in ["stop", "end"]:
                self.focus_launcher.stop_focus_session()
            launcher.hide()
            return True
        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle focus enter key"""
        if text == ">focus":
            self.focus_launcher.start_focus_session()
            launcher.hide()
            return True
        elif text in [">focus stop", ">focus end"]:
            self.focus_launcher.stop_focus_session()
            launcher.hide()
            return True
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle focus tab completion"""
        if text.startswith(">focus") or (text.startswith(">fo") and len(text) <= 4):
            if text == ">focus":
                return ">focus"
            elif text.startswith(">focus "):
                return text  # Keep existing text
            return ">focus"
        return None


class FocusLauncher(LauncherInterface):
    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.hook = FocusHook(self)
        self.focus_start_time = None
        self.focus_update_id = 0

        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, "hook_registry"):
            main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self):
        return ["focus"]

    @property
    def name(self):
        return "focus"

    def get_size_mode(self):
        return LauncherSizeMode.DEFAULT, None

    def handles_enter(self):
        return True

    def handle_enter(self, query: str, launcher_core) -> bool:
        if query == "":
            self.start_focus_session()
            launcher_core.hide()
            return True
        elif query in ["stop", "end"]:
            self.stop_focus_session()
            launcher_core.hide()
            return True
        return False

    def populate(self, query, launcher_core):
        action = query.strip()

        if action == "":
            # Show start option
            label_text = "Start focus session"
            metadata = "Click to start counting focus time"
            hook_data = "focus:start"
            launcher_core.add_launcher_result(
                label_text, metadata, index=1, action_data=hook_data
            )
        elif action in ["stop", "end"]:
            # Show stop option
            label_text = f"Stop focus session"
            metadata = "Click to stop current focus session"
            hook_data = f"focus:{action}"
            launcher_core.add_launcher_result(
                label_text, metadata, index=1, action_data=hook_data
            )
        else:
            # Invalid command
            label_text = "Usage: >focus or >focus stop"
            metadata = "Start a focus session or stop current one"
            launcher_core.add_launcher_result(label_text, metadata, index=1)

        launcher_core.current_apps = []

    def _run_hooks(self, hooks: List[Union[str, List[str]]]):
        """Run a list of hook commands.

        Args:
            hooks: List of commands, each can be a string or list of strings
        """
        # Clean environment for child processes
        env = dict(os.environ.items())
        env.pop("LD_PRELOAD", None)  # Remove LD_PRELOAD cause this breaks stuff

        for cmd in hooks:
            try:
                if isinstance(cmd, str):
                    # Run as shell command
                    subprocess.run(cmd, shell=True, env=env, check=False)
                elif isinstance(cmd, list):
                    # Run as command with arguments (no shell)
                    subprocess.run(cmd, env=env, check=False)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Silently fail if command fails
                pass

    def start_focus_session(self):
        """Start a focus session and begin counting elapsed time."""
        # Cancel any existing focus session
        if self.focus_update_id > 0:
            GLib.source_remove(self.focus_update_id)
            self.focus_update_id = 0

        self.focus_start_time = datetime.now()

        # Update status bar immediately
        self.update_focus_display()

        # Set up periodic updates every second
        self.focus_update_id = GLib.timeout_add_seconds(
            1, self.update_focus_status
        )

        # Run on_start hooks from config
        from core import config
        self._run_hooks(config.FOCUS_MODE_HOOKS.get("on_start", []))

        # Send notification
        self._send_notification("Focus session started", "Time tracking begun")

    def stop_focus_session(self):
        """Stop the current focus session and show summary."""
        if self.focus_update_id > 0:
            GLib.source_remove(self.focus_update_id)
            self.focus_update_id = 0

            if self.focus_start_time:
                elapsed = datetime.now() - self.focus_start_time
                hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)

                if hours > 0:
                    time_str = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    time_str = f"{minutes}m {seconds}s"
                else:
                    time_str = f"{seconds}s"

                # Send summary notification
                self._send_notification(
                    "Focus session ended",
                    f"Total time: {time_str}"
                )

                # Run on_stop hooks from config
                from core import config
                self._run_hooks(config.FOCUS_MODE_HOOKS.get("on_stop", []))

                # Clear status message after a short delay
                GLib.timeout_add_seconds(3, lambda: send_status_message("status:"))

            self.focus_start_time = None
        else:
            self._send_notification("No active focus session", "Start one with >focus")

    def update_focus_display(self):
        """Update the focus display with current elapsed time."""
        if self.focus_start_time:
            elapsed = datetime.now() - self.focus_start_time
            hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)

            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            send_status_message(f"status:Focus: {time_str}")

    def update_focus_status(self):
        """Update the focus status every second."""
        if self.focus_start_time:
            self.update_focus_display()
            return True  # Continue updating
        else:
            return False  # Stop updating

    def _send_notification(self, title: str, body: str):
        """Send a desktop notification."""
        # Clean environment for child processes
        env = dict(os.environ.items())
        env.pop("LD_PRELOAD", None)  # Remove LD_PRELOAD for child processes

        try:
            subprocess.run(
                ["notify-send", "-a", "Focus", title, body],
                env=env,
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Silently fail if notify-send is not available
            pass
