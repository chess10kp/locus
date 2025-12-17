# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import subprocess
from gi.repository import GLib
from utils import send_status_message


class TimerLauncher:
    def __init__(self, launcher):
        self.launcher = launcher

    def populate(self, time_str):
        if time_str:
            seconds = self.launcher.parse_time(time_str)
            if seconds is not None:
                label_text = f"Set timer for {time_str}"
                metadata = self.launcher.METADATA.get("timer", "")
                button = self.launcher.create_button_with_metadata(label_text, metadata)
                button.connect("clicked", self.on_timer_clicked, time_str)
            else:
                label_text = "Invalid time format (e.g., 5m)"
                metadata = self.launcher.METADATA.get("timer", "")
                button = self.launcher.create_button_with_metadata(label_text, metadata)
        else:
            label_text = "Usage: >timer 5m"
            metadata = self.launcher.METADATA.get("timer", "")
            button = self.launcher.create_button_with_metadata(label_text, metadata)
        self.launcher.list_box.append(button)
        self.launcher.current_apps = []

    def on_timer_clicked(self, button, time_str):
        self.start_timer(time_str)
        self.launcher.hide()

    def start_timer(self, time_str):
        seconds = self.launcher.parse_time(time_str)
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
            subprocess.run(["notify-send", "-a", "Timer", f"set for {time_str}"])
        else:
            subprocess.run(["notify-send", "Invalid time format"])

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
        subprocess.run(["notify-send", "-a", "Timer", "-t", "3000", "timer complete"])
        sound_path = "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"
        subprocess.Popen(["mpv", "--no-video", sound_path])
        return False
