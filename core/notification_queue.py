# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore
# ruff: noqa: E402

from typing import Optional, Dict, TYPE_CHECKING
from enum import Enum

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GLib", "2.0")

from core.notification_store import Notification, get_notification_store

if TYPE_CHECKING:
    from core.notification_banner import NotificationBanner


class Corner(Enum):
    """Screen corner for notification positioning."""

    TOP_LEFT = "top-left"
    TOP_RIGHT = "top-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_RIGHT = "bottom-right"


class NotificationQueue:
    """Manager for notification banner queue and positioning."""

    _instance: Optional["NotificationQueue"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self.store = get_notification_store()
        self.active_banners: Dict[str, "NotificationBanner"] = {}
        self.max_banners = 5
        self.banner_gap = 10
        self.banner_height = 100
        self.corner = Corner.TOP_RIGHT
        self._initialized = True

        self._setup_store_signals()

    def _setup_store_signals(self) -> None:
        """Set up signals from notification store."""
        from core.config import NOTIFICATION_DAEMON_CONFIG

        self.corner = Corner(NOTIFICATION_DAEMON_CONFIG.get("position", "top-right"))

    def show_notification(self, notification: Notification) -> None:
        """Show a notification as a banner."""
        if notification.id in self.active_banners:
            return

        if len(self.active_banners) >= self.max_banners:
            oldest_id = list(self.active_banners.keys())[0]
            self._close_banner(oldest_id)

        from core.notification_banner import NotificationBanner

        banner = NotificationBanner(
            notification=notification,
            on_close=self._on_banner_closed,
            application=None,
        )

        self.active_banners[notification.id] = banner
        banner.show()

        self._reposition_all_banners()

    def _on_banner_closed(self, notification_id: str) -> None:
        """Handle banner close."""
        if notification_id in self.active_banners:
            del self.active_banners[notification_id]
            self._reposition_all_banners()

    def _close_banner(self, notification_id: str) -> None:
        """Close a specific banner."""
        if notification_id in self.active_banners:
            banner = self.active_banners.pop(notification_id)
            banner.dismiss()

    def _reposition_all_banners(self) -> None:
        """Reposition all active banners."""
        banners = list(self.active_banners.values())
        for i, banner in enumerate(banners):
            self._position_banner(banner, i)

    def _position_banner(self, banner: "NotificationBanner", index: int) -> None:
        """Position a banner based on corner setting."""
        from gi.repository import Gtk4LayerShell as GtkLayerShell

        LayerShell = GtkLayerShell
        Layer = GtkLayerShell.Layer
        Edge = GtkLayerShell.Edge

        top_margin = 40 + (index * (self.banner_height + self.banner_gap))
        right_margin = 10

        if self.corner == Corner.TOP_LEFT:
            banner.update_position(right_margin, top_margin)
        elif self.corner == Corner.TOP_RIGHT:
            banner.update_position(right_margin, top_margin)
        elif self.corner == Corner.BOTTOM_LEFT:
            LayerShell.set_anchor(banner, Edge.TOP, False)
            LayerShell.set_anchor(banner, Edge.BOTTOM, True)
            bottom_margin = 10 + (index * (self.banner_height + self.banner_gap))
            LayerShell.set_margin(banner, Edge.BOTTOM, bottom_margin)
            LayerShell.set_margin(banner, Edge.RIGHT, right_margin)
        elif self.corner == Corner.BOTTOM_RIGHT:
            LayerShell.set_anchor(banner, Edge.TOP, False)
            LayerShell.set_anchor(banner, Edge.BOTTOM, True)
            bottom_margin = 10 + (index * (self.banner_height + self.banner_gap))
            LayerShell.set_margin(banner, Edge.BOTTOM, bottom_margin)
            LayerShell.set_margin(banner, Edge.RIGHT, right_margin)

    def dismiss_all(self) -> None:
        """Dismiss all active banners."""
        for banner in list(self.active_banners.values()):
            banner.dismiss()
        self.active_banners.clear()

    def set_corner(self, corner: Corner) -> None:
        """Set the corner for banner positioning."""
        self.corner = corner
        self._reposition_all_banners()

    def get_active_count(self) -> int:
        """Get the number of active banners."""
        return len(self.active_banners)

    def cleanup(self) -> None:
        """Clean up resources."""
        self.dismiss_all()


_notification_queue_instance: Optional[NotificationQueue] = None


def get_notification_queue() -> NotificationQueue:
    """Get the singleton notification queue instance."""
    global _notification_queue_instance
    if _notification_queue_instance is None:
        _notification_queue_instance = NotificationQueue()
    return _notification_queue_instance
