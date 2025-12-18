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
from gi.repository import GLib
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from typing import Any, Optional, Tuple
from utils import send_status_message


class TimerHook(LauncherHook):
    def __init__(self, timer_launcher):
        self.timer_launcher = timer_launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """Handle timer button clicks"""
        if isinstance(item_data, str) and item_data.startswith("timer:"):
            time_str = item_data[6:]  # Remove "timer:" prefix
            self.timer_launcher.start_timer(time_str)
            launcher.hide()
            return True
        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle timer enter key"""
        if text.startswith(">timer "):
            time_str = text[6:].strip()
            self.timer_launcher.start_timer(time_str)
            launcher.hide()
            return True
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle timer tab completion"""
        if text.startswith(">timer") or (text.startswith(">ti") and len(text) <= 4):
            return ">timer "
        return None


class TimerLauncher(LauncherInterface):
    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.hook = TimerHook(self)

        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, 'hook_registry'):
            main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self):
        return ["timer"]

    @property
    def name(self):
        return "timer"

    def get_size_mode(self):
        return LauncherSizeMode.DEFAULT, None

    def handles_enter(self):
        return True

    def handle_enter(self, query: str, launcher_core) -> bool:
        if query:
            self.start_timer(query)
            launcher_core.hide()
            return True
        return False

    def populate(self, query, launcher_core):
        time_str = query
        if time_str:
            seconds = launcher_core.parse_time(time_str)
            if seconds is not None:
                label_text = f"Set timer for {time_str}"
                metadata = "Click to start timer"
                hook_data = f"timer:{time_str}"
                button = launcher_core.create_button_with_metadata(
                    label_text, metadata, hook_data
                )
            else:
                label_text = "Invalid time format (e.g., 5m)"
                metadata = "Use format like 5m, 1h, 30s"
                button = launcher_core.create_button_with_metadata(label_text, metadata)
        else:
            label_text = "Usage: >timer 5m"
            metadata = "Enter time duration (e.g., 5m, 1h, 30s)"
            button = launcher_core.create_button_with_metadata(label_text, metadata)
        launcher_core.list_box.append(button)
        launcher_core.current_apps = []

    def on_timer_clicked(self, button, time_str):
        self.start_timer(time_str)
        if self.launcher:
            self.launcher.hide()

    def start_timer(self, time_str):
        # Use launcher_core reference if available, otherwise fallback
        parse_func = self.launcher.parse_time if self.launcher else None
        if not parse_func:
            # Import parse_time function directly
            from core.launcher import parse_time
            parse_func = parse_time

        seconds = parse_func(time_str)
        # Clean environment for child processes
        env = dict(os.environ.items())
        env.pop("LD_PRELOAD", None)  # Remove LD_PRELOAD for child processes

        if seconds is not None:
            # Cancel any existing timer
            if self.launcher.timer_update_id > 0:
                GLib.source_remove(self.launcher.timer_update_id)
                self.launcher.timer_update_id = 0
            self.launcher.timer_remaining = seconds
            # Update status bar immediately with initial time
            self.update_timer_display()
            # Set up periodic updates every second
            self.launcher.timer_update_id = GLib.timeout_add_seconds(
                1, self.update_timer_status
            )
            # Set the final timeout
            GLib.timeout_add_seconds(seconds, self.on_timer_done)
            subprocess.run(["notify-send", "-a", "Timer", f"set for {time_str}"], env=env)
        else:
            subprocess.run(["notify-send", "Invalid time format"], env=env)

    def update_timer_display(self):
        """Update the timer display without decrementing the counter."""
        minutes, seconds = divmod(self.launcher.timer_remaining, 60)
        time_str = f"{minutes:02d}:{seconds:02d}"
        send_status_message(f"Timer: {time_str}")

    def update_timer_status(self):
        if self.launcher.timer_remaining > 0:
            self.launcher.timer_remaining -= 1
            self.update_timer_display()
            return True  # Continue updating
        else:
            # Timer finished, clear status and reset
            send_status_message("")
            self.launcher.timer_update_id = 0
            return False  # Stop updating

    def on_timer_done(self):
        # Clear the status message
        send_status_message("")
        # Clean environment for child processes
        env = dict(os.environ.items())
        env.pop("LD_PRELOAD", None)  # Remove LD_PRELOAD for child processes
        subprocess.run(["notify-send", "-a", "Timer", "-t", "3000", "timer complete"], env=env)
        sound_path = "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"
        subprocess.Popen(["mpv", "--no-video", sound_path], env=env)
        return False
