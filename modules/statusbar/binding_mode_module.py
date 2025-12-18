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


class BindingModeModule(StatusbarModuleInterface):
    """Statusbar module for displaying current Sway binding mode."""

    def __init__(self, interval: int = 1, wm_client=None):
        self._interval = interval
        self.wm_client = wm_client

    @property
    def name(self) -> str:
        return "binding_mode"

    @property
    def update_mode(self) -> StatusbarUpdateMode:
        return StatusbarUpdateMode.PERIODIC

    @property
    def update_interval(self) -> Optional[int]:
        return self._interval

    def create_widget(self) -> Gtk.Widget:
        label = Gtk.Label()
        label.set_name("binding-mode-label")
        # Initial update
        self.update(label)
        return label

    def update(self, widget: Gtk.Widget) -> None:
        try:
            if self.wm_client:
                binding_mode = self.wm_client.get_binding_mode()
                if binding_mode and binding_mode != "default":
                    widget.set_text(f"[{binding_mode}]")
                    widget.set_visible(True)
                else:
                    widget.set_text("")
                    widget.set_visible(False)
            else:
                # Fallback to swaymsg
                result = subprocess.run(
                    ["swaymsg", "-t", "get_inputs"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )

                if result.returncode == 0:
                    # Parse binding mode from swaymsg output
                    import json

                    data = json.loads(result.stdout)
                    for input_device in data:
                        if "current_mode" in input_device:
                            mode = input_device["current_mode"]
                            if mode and mode != "default":
                                widget.set_text(f"[{mode}]")
                                widget.set_visible(True)
                                return

                    # No non-default mode found
                    widget.set_text("")
                    widget.set_visible(False)
                else:
                    widget.set_text("")
                    widget.set_visible(False)
        except Exception:
            widget.set_text("")
            widget.set_visible(False)

    def get_size_mode(self) -> Tuple[StatusbarSizeMode, Optional[Tuple[int, int]]]:
        return StatusbarSizeMode.DEFAULT, None

    def get_styles(self) -> Optional[str]:
        return """
        #binding-mode-label {
            padding: 0 8px;
            font-size: 12px;
            font-weight: 500;
            color: #ff79c6;
            background: rgba(255, 121, 198, 0.1);
            border-radius: 4px;
            margin: 0 4px;
        }
        """
