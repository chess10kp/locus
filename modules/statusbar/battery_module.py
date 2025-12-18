# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import subprocess
from typing import Tuple, Optional

from gi.repository import Gtk

from core.statusbar_interface import (
    StatusbarModuleInterface,
    StatusbarUpdateMode,
    StatusbarSizeMode,
)


class BatteryModule(StatusbarModuleInterface):
    """Statusbar module for displaying battery status."""

    def __init__(self, interval: int = 60, show_percentage: bool = True):
        self._interval = interval
        self._show_percentage = show_percentage

    @property
    def name(self) -> str:
        return "battery"

    @property
    def update_mode(self) -> StatusbarUpdateMode:
        return StatusbarUpdateMode.PERIODIC

    @property
    def update_interval(self) -> Optional[int]:
        return self._interval

    def create_widget(self) -> Gtk.Widget:
        label = Gtk.Label()
        label.set_name("battery-label")
        # Initial update
        self.update(label)
        return label

    def update(self, widget: Gtk.Widget) -> None:
        try:
            # Get battery status using the utility function
            battery_info = self._get_battery_status()
            if battery_info:
                icon = battery_info["icon"]
                percentage = battery_info["percentage"]

                if self._show_percentage:
                    text = f"{icon} {percentage}%"
                else:
                    text = icon

                widget.set_text(text)
            else:
                widget.set_text("󰂃")
        except Exception:
            widget.set_text("󰂃")

    def _get_battery_status(self) -> Optional[dict]:
        """Get battery status information."""
        try:
            # Try to get battery info using upower
            result = subprocess.run(
                ["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                lines = result.stdout.split("\n")
                percentage = None
                state = None

                for line in lines:
                    line = line.strip()
                    if "percentage:" in line.lower():
                        percentage = line.split(":")[1].strip().replace("%", "")
                    elif "state:" in line.lower():
                        state = line.split(":")[1].strip().lower()

                if percentage is not None and state is not None:
                    # Determine icon based on percentage and state
                    perc = int(percentage)
                    if state in ["charging", "fully-charged"]:
                        if perc >= 90:
                            icon = "󰂋"
                        elif perc >= 70:
                            icon = "󰂊"
                        elif perc >= 50:
                            icon = "󰢞"
                        elif perc >= 30:
                            icon = "󰂉"
                        else:
                            icon = "󰢜"
                    else:
                        if perc >= 90:
                            icon = "󰁹"
                        elif perc >= 70:
                            icon = "󰂁"
                        elif perc >= 50:
                            icon = "󰂀"
                        elif perc >= 30:
                            icon = "󰁿"
                        elif perc >= 10:
                            icon = "󰁾"
                        else:
                            icon = "󰁼"

                    return {"icon": icon, "percentage": perc, "state": state}

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            # Fallback to basic battery check
            try:
                with open("/sys/class/power_supply/BAT0/capacity", "r") as f:
                    percentage = int(f.read().strip())

                with open("/sys/class/power_supply/BAT0/status", "r") as f:
                    status = f.read().strip().lower()

                # Simple icon determination
                if "charging" in status or "full" in status:
                    icon = "󰂈"
                elif percentage >= 75:
                    icon = "󰁹"
                elif percentage >= 50:
                    icon = "󰂂"
                elif percentage >= 25:
                    icon = "󰁻"
                else:
                    icon = "󰁺"

                return {"icon": icon, "percentage": percentage, "state": status}
            except (IOError, ValueError):
                pass

        return None

    def get_size_mode(self) -> Tuple[StatusbarSizeMode, Optional[Tuple[int, int]]]:
        return StatusbarSizeMode.DEFAULT, None

    def get_styles(self) -> Optional[str]:
        return """
        #battery-label {
            padding: 0 8px;
            font-size: 14px;
            font-weight: 500;
        }
        """
