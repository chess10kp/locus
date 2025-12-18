# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from typing import Tuple, Optional
from gi.repository import Gtk

from core.statusbar_interface import (
    StatusbarModuleInterface,
    StatusbarUpdateMode,
    StatusbarSizeMode,
)


class LauncherModule(StatusbarModuleInterface):
    """Statusbar module for the launcher button."""

    @property
    def name(self) -> str:
        return "launcher"

    @property
    def update_mode(self) -> StatusbarUpdateMode:
        return StatusbarUpdateMode.STATIC

    def create_widget(self) -> Gtk.Widget:
        button = Gtk.Button(label="󰀻")
        button.set_name("launcher-button")
        return button

    def update(self, widget: Gtk.Widget) -> None:
        # Static module doesn't need updates
        pass

    def get_size_mode(self) -> Tuple[StatusbarSizeMode, Optional[Tuple[int, int]]]:
        return StatusbarSizeMode.DEFAULT, None

    def get_styles(self) -> Optional[str]:
        return """
        #launcher-button {
            border: none;
            background: none;
            padding: 6px 12px;
            font-size: 24px;
            color: #f8f8f2;
            transition: all 0.2s ease;
        }
        #launcher-button:hover {
            color: #50fa7b;
        }
        #launcher-button:active {
            color: #8be9fd;
        }
        """

    def handles_clicks(self) -> bool:
        return True

    def handle_click(self, widget: Gtk.Widget, event) -> bool:
        """Handle launcher button click."""
        # In GTK4, we use 'clicked' signal instead of 'button-press-event'
        # Import here to avoid circular imports
        from core.launcher import Launcher

        # Create and show the launcher
        launcher = Launcher()
        launcher.present()
        return True
