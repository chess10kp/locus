# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore
from launchers.lock_launcher import apply_styles

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
        button = Gtk.Button(label="Launch")
        button.set_name("launcher-button")
        button.add_css_class("launcher-button")
        return button

    def update(self, widget: Gtk.Widget) -> None:
        # Static module doesn't need updates
        pass

    def get_size_mode(self) -> Tuple[StatusbarSizeMode, Optional[Tuple[int, int]]]:
        return StatusbarSizeMode.DEFAULT, None

    def handles_clicks(self) -> bool:
        return True

    def get_styles(self) -> Optional[str]:
        return """
        #launcher-button {
            font-size: 16px;
        }
        """

    def handle_click(self, widget: Gtk.Widget, event) -> bool:
        """Handle launcher button click."""
        # In GTK4, we use 'clicked' signal instead of 'button-press-event'
        # Import here to avoid circular imports
        from core import status_bars

        # Use the existing launcher instance from the first status bar
        # instead of creating a new one
        if status_bars and len(status_bars) > 0 and status_bars[0].launcher:
            status_bars[0].launcher.present()
            return True

        # Fallback: create new launcher if status bar launcher doesn't exist
        from core.launcher import Launcher

        app = widget.get_root().get_application()
        launcher = Launcher(application=app)
        launcher.present()
        return True
