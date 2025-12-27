# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from abc import ABC, abstractmethod
from typing import Optional, Tuple
from enum import Enum
from gi.repository import Gtk


class StatusbarUpdateMode(Enum):
    """Update modes for statusbar modules."""

    STATIC = "static"  # Never updates (launcher button)
    PERIODIC = "periodic"  # Updates on interval (time, battery)
    EVENT_DRIVEN = "event"  # Updates on events (workspaces)
    ON_DEMAND = "on_demand"  # Updates when requested (custom_message)


class StatusbarSizeMode(Enum):
    """Size modes for statusbar modules."""

    DEFAULT = "default"
    CUSTOM = "custom"


class StatusbarModuleInterface(ABC):
    """Abstract interface that all statusbar modules must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of this module."""
        pass

    @property
    @abstractmethod
    def update_mode(self) -> StatusbarUpdateMode:
        """Return how this module updates its content."""
        pass

    @property
    def update_interval(self) -> Optional[int]:
        """Return update interval in seconds for PERIODIC modules."""
        return None

    @abstractmethod
    def create_widget(self) -> Gtk.Widget:
        """Create and return the GTK widget for this module."""
        pass

    @abstractmethod
    def update(self, widget: Gtk.Widget) -> None:
        """Update the widget content. Called based on update_mode."""
        pass

    @abstractmethod
    def get_size_mode(self) -> Tuple[StatusbarSizeMode, Optional[Tuple[int, int]]]:
        """Return the size mode and optional custom size for this module.

        Returns:
            Tuple of (size_mode, optional_custom_size)
        """
        pass

    def get_styles(self) -> Optional[str]:
        """Return CSS styles for this module, or None for default."""
        return None

    def get_separator_style(self) -> Optional[str]:
        """Return CSS styles for separator after this module."""
        return None

    def handles_clicks(self) -> bool:
        """Return True if this module handles click events."""
        return False

    def handle_click(self, widget: Gtk.Widget, event) -> bool:
        """Handle click events. Return True if handled.
        Only called if handles_clicks() returns True.
        """
        return False

    def handles_ipc_messages(self) -> bool:
        """Return True if this module handles IPC messages."""
        return False

    def handle_ipc_message(self, message: str, widget: Gtk.Widget) -> bool:
        """Handle IPC messages. Return True if handled.
        Only called if handles_ipc_messages() returns True.
        """
        return False

    def cleanup(self) -> None:
        """Clean up resources when module is being unregistered."""
        pass