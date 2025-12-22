# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import json
import os
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from gi.repository import GLib


@dataclass
class Notification:
    """Represents a desktop notification."""

    id: str  # Unique notification ID
    app_name: str  # Application name
    app_icon: str  # Icon name or path
    summary: str  # Notification title
    body: str  # Notification body text
    actions: List[str]  # Available actions
    hints: Dict[str, Any]  # Extra hints (urgency, category, etc.)
    timestamp: datetime  # When received
    expire_timeout: int  # milliseconds until expiry
    read: bool = False  # Read status

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime to ISO string
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Notification":
        """Create from dictionary (JSON deserialization)."""
        # Convert ISO string back to datetime
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class NotificationStore:
    """Centralized storage and management of notification history."""

    _instance: Optional["NotificationStore"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure only one store exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        max_history: int = 500,
        max_age_days: int = 30,
        persist_path: Optional[str] = None,
    ):
        """Initialize the notification store.

        Args:
            max_history: Maximum number of notifications to store
            max_age_days: Maximum age in days before auto-deletion
            persist_path: Path to JSON file for persistence
        """
        # Avoid re-initializing if already initialized
        if hasattr(self, "_initialized"):
            return

        self.max_history = max_history
        self.max_age_days = max_age_days
        self.notifications: List[Notification] = []
        self._lock = threading.RLock()

        # Set up persistence path
        if persist_path is None:
            cache_dir = Path.home() / ".cache" / "locus"
            cache_dir.mkdir(parents=True, exist_ok=True)
            persist_path = str(cache_dir / "notification_history.json")

        self.persist_path = persist_path

        # Load from disk if exists
        self.load_from_disk()

        # Clean up old notifications on startup
        self.cleanup_expired()

        self._initialized = True

    def add_notification(self, notification: Notification) -> None:
        """Add a notification to the store.

        Args:
            notification: The notification to add
        """
        with self._lock:
            # Add to beginning of list (most recent first)
            self.notifications.insert(0, notification)

            # Enforce max history limit
            if len(self.notifications) > self.max_history:
                self.notifications = self.notifications[: self.max_history]

            # Emit signal for unread count update
            GLib.idle_add(self._emit_notification_added, notification.id)

    def get_recent_notifications(self, limit: int = 50) -> List[Notification]:
        """Get recent notifications.

        Args:
            limit: Maximum number of notifications to return

        Returns:
            List of recent notifications
        """
        with self._lock:
            return self.notifications[:limit]

    def get_notifications_by_app(self, app_name: str) -> List[Notification]:
        """Get notifications from a specific application.

        Args:
            app_name: Application name to filter by

        Returns:
            List of notifications from the app
        """
        with self._lock:
            return [n for n in self.notifications if n.app_name == app_name]

    def get_unread_notifications(self) -> List[Notification]:
        """Get all unread notifications.

        Returns:
            List of unread notifications
        """
        with self._lock:
            return [n for n in self.notifications if not n.read]

    def get_notification_by_id(self, notification_id: str) -> Optional[Notification]:
        """Get a specific notification by ID.

        Args:
            notification_id: ID of the notification

        Returns:
            Notification if found, None otherwise
        """
        with self._lock:
            for notif in self.notifications:
                if notif.id == notification_id:
                    return notif
            return None

    def remove_notification(self, notification_id: str) -> bool:
        """Remove a notification by ID.

        Args:
            notification_id: ID of the notification to remove

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            for i, notif in enumerate(self.notifications):
                if notif.id == notification_id:
                    self.notifications.pop(i)
                    GLib.idle_add(self._emit_notification_removed, notification_id)
                    return True
            return False

    def mark_as_read(self, notification_id: str) -> bool:
        """Mark a notification as read.

        Args:
            notification_id: ID of the notification

        Returns:
            True if marked, False if not found
        """
        with self._lock:
            for notif in self.notifications:
                if notif.id == notification_id:
                    if not notif.read:
                        notif.read = True
                        GLib.idle_add(self._emit_unread_count_changed)
                    return True
            return False

    def mark_all_as_read(self) -> int:
        """Mark all notifications as read.

        Returns:
            Number of notifications marked as read
        """
        with self._lock:
            count = 0
            for notif in self.notifications:
                if not notif.read:
                    notif.read = True
                    count += 1
            if count > 0:
                GLib.idle_add(self._emit_unread_count_changed)
            return count

    def clear_all(self) -> int:
        """Clear all notifications.

        Returns:
            Number of notifications cleared
        """
        with self._lock:
            count = len(self.notifications)
            self.notifications.clear()
            GLib.idle_add(self._emit_notifications_cleared)
            return count

    def search(self, query: str) -> List[Notification]:
        """Search notifications by text.

        Args:
            query: Search query string

        Returns:
            List of matching notifications
        """
        if not query:
            return []

        query_lower = query.lower()
        with self._lock:
            return [
                n
                for n in self.notifications
                if query_lower in n.summary.lower()
                or query_lower in n.body.lower()
                or query_lower in n.app_name.lower()
            ]

    def get_unread_count(self) -> int:
        """Get the count of unread notifications.

        Returns:
            Number of unread notifications
        """
        with self._lock:
            return sum(1 for n in self.notifications if not n.read)

    def cleanup_expired(self) -> int:
        """Remove expired and old notifications.

        Returns:
            Number of notifications removed
        """
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(days=self.max_age_days)

            original_count = len(self.notifications)
            # Only remove by age (max_age_days), not by expire_timeout
            # expire_timeout is for display duration, not storage duration
            self.notifications = [
                n for n in self.notifications if n.timestamp > cutoff
            ]

            removed = original_count - len(self.notifications)
            if removed > 0:
                GLib.idle_add(self._emit_notifications_cleared)
            return removed

    def _is_expired(self, notification: Notification, now: datetime) -> bool:
        """Check if a notification is expired.

        Args:
            notification: Notification to check
            now: Current datetime

        Returns:
            True if expired, False otherwise
        """
        # expire_timeout of -1 means never expire
        if notification.expire_timeout == -1:
            return False

        # 0 means expire immediately (should already be handled by daemon)
        if notification.expire_timeout == 0:
            return True

        # Calculate expiry time
        expire_time = notification.timestamp + timedelta(
            milliseconds=notification.expire_timeout
        )
        return now > expire_time

    def save_to_disk(self) -> bool:
        """Save notifications to disk.

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            try:
                data = {
                    "notifications": [n.to_dict() for n in self.notifications],
                    "version": 1,
                }
                with open(self.persist_path, "w") as f:
                    json.dump(data, f, indent=2)
                return True
            except Exception as e:
                print(f"Error saving notification history: {e}")
                return False

    def load_from_disk(self) -> bool:
        """Load notifications from disk.

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            try:
                if not os.path.exists(self.persist_path):
                    return False

                with open(self.persist_path, "r") as f:
                    data = json.load(f)

                # Load notifications
                if "notifications" in data:
                    self.notifications = [
                        Notification.from_dict(n) for n in data["notifications"]
                    ]

                return True
            except Exception as e:
                print(f"Error loading notification history: {e}")
                return False

    # Signal emissions (to be connected by UI components)

    def _emit_notification_added(self, notification_id: str) -> None:
        """Emit notification-added signal."""
        pass  # Will be overridden by signal connections

    def _emit_notification_removed(self, notification_id: str) -> None:
        """Emit notification-removed signal."""
        pass

    def _emit_notifications_cleared(self) -> None:
        """Emit notifications-cleared signal."""
        pass

    def _emit_unread_count_changed(self) -> None:
        """Emit unread-count-changed signal."""
        pass


# Singleton accessor function
_notification_store_instance: Optional[NotificationStore] = None


def get_notification_store() -> NotificationStore:
    """Get the singleton notification store instance."""
    global _notification_store_instance
    if _notification_store_instance is None:
        _notification_store_instance = NotificationStore()
    return _notification_store_instance
