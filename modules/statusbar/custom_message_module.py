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


class CustomMessageModule(StatusbarModuleInterface):
    """Statusbar module for displaying custom IPC messages."""

    def __init__(self):
        self.current_message = ""

    @property
    def name(self) -> str:
        return "custom_message"

    @property
    def update_mode(self) -> StatusbarUpdateMode:
        return StatusbarUpdateMode.ON_DEMAND

    def create_widget(self) -> Gtk.Widget:
        label = Gtk.Label()
        label.set_name("custom-message-label")
        return label

    def update(self, widget: Gtk.Widget) -> None:
        widget.set_text(self.current_message)
        # Show/hide based on whether there's a message
        widget.set_visible(bool(self.current_message))

    def get_size_mode(self) -> Tuple[StatusbarSizeMode, Optional[Tuple[int, int]]]:
        return StatusbarSizeMode.DEFAULT, None

    def handles_ipc_messages(self) -> bool:
        return True

    def handle_ipc_message(self, message: str, widget: Gtk.Widget) -> bool:
        """Handle IPC message for custom status display."""
        if message.startswith("status:"):
            # Extract the actual status message
            status_text = message[7:]  # Remove "status:" prefix
            self.current_message = status_text
            self.update(widget)
            return True
        return False

    def get_styles(self) -> Optional[str]:
        return """
        #custom-message-label {
            padding: 0 8px;
            font-size: 12px;
            font-weight: 500;
            color: #f1fa8c;
            background: #0e1419;
            border-radius: 4px;
        }
        """
