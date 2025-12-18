# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from datetime import datetime as dt
from typing import Tuple, Optional

from gi.repository import Gtk

from core.statusbar_interface import (
    StatusbarModuleInterface,
    StatusbarUpdateMode,
    StatusbarSizeMode,
)


class TimeModule(StatusbarModuleInterface):
    """Statusbar module for displaying current time."""

    def __init__(self, format: str = "%H:%M", interval: int = 60):
        self.format = format
        self._interval = interval

    @property
    def name(self) -> str:
        return "time"

    @property
    def update_mode(self) -> StatusbarUpdateMode:
        return StatusbarUpdateMode.PERIODIC

    @property
    def update_interval(self) -> Optional[int]:
        return self._interval

    def create_widget(self) -> Gtk.Widget:
        label = Gtk.Label()
        label.set_name("time-label")
        # Initial update
        self.update(label)
        return label

    def update(self, widget: Gtk.Widget) -> None:
        current_time = dt.now().strftime(self.format)
        widget.set_text(current_time)

    def get_size_mode(self) -> Tuple[StatusbarSizeMode, Optional[Tuple[int, int]]]:
        return StatusbarSizeMode.DEFAULT, None

    def get_styles(self) -> Optional[str]:
        return """
        #time-label {
            padding: 0 8px;
            font-size: 14px;
            font-weight: 500;
        }
        """
