# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import socket
from typing import Tuple, Optional
from gi.repository import Gtk

from core.statusbar_interface import (
    StatusbarModuleInterface,
    StatusbarUpdateMode,
    StatusbarSizeMode,
)
from core.config import SOCKET_PATH


class NotificationModule(StatusbarModuleInterface):
    """Statusbar module for notification icon with unread count badge."""

    def __init__(self, interval: int = 30):
        """Initialize the notification module.

        Args:
            interval: Update interval in seconds (not used for EVENT_DRIVEN mode)
        """
        # Import here to avoid circular imports
        from core.notification_store import get_notification_store

        self.store = get_notification_store()
        self.unread_count = 0
        self._update_unread_count()

    @property
    def name(self) -> str:
        return "notifications"

    @property
    def update_mode(self) -> StatusbarUpdateMode:
        return StatusbarUpdateMode.EVENT_DRIVEN

    def create_widget(self) -> Gtk.Widget:
        """Create the notification icon button."""
        # Create button with initial label
        button = Gtk.Button(label="󰂚")
        button.set_name("notification-button")
        return button

    def update(self, widget: Gtk.Widget) -> None:
        """Update the notification icon and badge."""
        # Update unread count
        self._update_unread_count()

        # Check if widget is a button
        if not isinstance(widget, Gtk.Button):
            return

        # Update button label based on unread count
        if self.unread_count > 0:
            if self.unread_count > 99:
                widget.set_label("󰂟 99+")
            else:
                widget.set_label(f"󰂟 {self.unread_count}")
        else:
            widget.set_label("󰂚")

    def get_size_mode(self) -> Tuple[StatusbarSizeMode, Optional[Tuple[int, int]]]:
        return StatusbarSizeMode.DEFAULT, None

    def get_styles(self) -> Optional[str]:
        """Return CSS styles for the notification icon."""
        return """
        #notification-button {
            border: none;
            background: none;
            padding: 6px 12px;
            font-size: 18px;
            color: #f8f8f2;
        }
        #notification-button:hover {
            color: #50fa7b;
        }
        #notification-button:active {
            color: #8be9fd;
        }
        """

    def handles_clicks(self) -> bool:
        return True

    def handle_click(self, widget: Gtk.Widget, event) -> bool:
        """Handle notification button click - open notification launcher."""
        try:
            # Send IPC message to open notification launcher
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(SOCKET_PATH)
            sock.sendall(">notifications".encode())
            sock.close()
            return True
        except Exception as e:
            print(f"Error opening notification launcher: {e}")
            return False

    def _update_unread_count(self) -> None:
        """Update the unread count from the store."""
        self.unread_count = self.store.get_unread_count()
