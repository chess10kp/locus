# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from datetime import datetime
from typing import Any, Optional, List, Dict, Tuple
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from utils.notification_utils import truncate_text


class NotificationHook(LauncherHook):
    """Hook for handling notification launcher interactions."""

    def __init__(self, notification_launcher):
        self.notification_launcher = notification_launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """Handle notification item selection."""
        if isinstance(item_data, dict):
            item_type = item_data.get("type")

            if item_type == "notification_item":
                notification_id = item_data.get("notification_id")
                action = item_data.get("action")

                if action == "mark_read":
                    self.notification_launcher.mark_as_read(notification_id)
                    # Refresh the view
                    launcher.populate_apps(launcher.search_entry.get_text())
                elif action == "dismiss":
                    self.notification_launcher.dismiss(notification_id)
                    # Refresh the view
                    launcher.populate_apps(launcher.search_entry.get_text())
                elif action == "open":
                    # Just mark as read and close
                    self.notification_launcher.mark_as_read(notification_id)
                    launcher.hide()

                return True

            elif item_type == "filter_button":
                filter_type = item_data.get("filter")
                # Update search text to show filter
                current_text = launcher.search_entry.get_text()
                # Set text to trigger filter
                if filter_type == "all":
                    launcher.search_entry.set_text(">notifications")
                elif filter_type == "today":
                    launcher.search_entry.set_text(">notifications today")
                elif filter_type == "unread":
                    launcher.search_entry.set_text(">notifications unread")
                launcher.populate_apps(launcher.search_entry.get_text())
                return True

            elif item_type == "action_button":
                action = item_data.get("action")
                if action == "clear_all":
                    self.notification_launcher.clear_all()
                    launcher.populate_apps(launcher.search_entry.get_text())
                elif action == "mark_all_read":
                    self.notification_launcher.mark_all_as_read()
                    launcher.populate_apps(launcher.search_entry.get_text())
                elif action == "refresh":
                    launcher.populate_apps(launcher.search_entry.get_text())
                return True

        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle enter key on notification commands."""
        if text.startswith(">notifications"):
            query = text[13:].strip()

            # Handle command shortcuts
            if query == "clear" or query == "clear all":
                self.notification_launcher.clear_all()
                launcher.hide()
                return True
            elif query == "read" or query == "mark read":
                self.notification_launcher.mark_all_as_read()
                launcher.hide()
                return True

        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle tab completion."""
        if text.startswith(">notifications"):
            query = text[13:].strip()
            # Could implement completion for filters
            if query in ["", "to"]:
                return ">notifications today"
            elif query in ["u", "un"]:
                return ">notifications unread"
        return None


class NotificationLauncher(LauncherInterface):
    """Launcher for notification history and management."""

    def __init__(self, main_launcher=None):
        """Initialize the notification launcher.

        Args:
            main_launcher: Reference to the main launcher (optional)
        """
        if main_launcher:
            self.hook = NotificationHook(self)
            main_launcher.hook_registry.register_hook(self.hook)

        # Import here to avoid circular imports
        from core.notification_store import get_notification_store

        self.store = get_notification_store()

    @property
    def command_triggers(self) -> list:
        return ["notifications", "notif", "nn"]

    @property
    def name(self) -> str:
        return "notifications"

    def get_size_mode(self) -> Tuple[LauncherSizeMode, Optional[Tuple[int, int]]]:
        return LauncherSizeMode.DEFAULT, None

    def populate(self, query: str, launcher_core) -> None:
        """Populate the notification menu.

        Args:
            query: The query string (without trigger prefix)
            launcher_core: Reference to the main launcher for UI operations
        """
        # Parse query for filters
        filter_type = "all"  # all, today, unread
        search_query = ""

        if query:
            parts = query.split(None, 1)
            first_part = parts[0].lower() if parts else ""

            if first_part in ["today", "unread"]:
                filter_type = first_part
                search_query = parts[1] if len(parts) > 1 else ""
            else:
                search_query = query

        # Get notifications based on filter
        notifications = self._get_notifications(filter_type, search_query)

        # Add header with counts
        unread_count = self.store.get_unread_count()
        total_count = len(self.store.get_recent_notifications(limit=1000))

        self._add_header(
            f"🔔 Notifications ({unread_count} unread, {total_count} total)",
            launcher_core,
        )

        # Add filter buttons
        self._add_filter_buttons(filter_type, launcher_core)

        # Add notifications
        if not notifications:
            launcher_core.add_launcher_result(
                text="No notifications",
                subtitle="Clear to close"
                if filter_type == "all"
                else "Try '>notifications' to see all",
                index=None,
            )
        else:
            # Group by app
            grouped = self._group_by_app(notifications)

            index = 1
            for app_name, notifs in grouped.items():
                # Add app header if multiple apps
                if len(grouped) > 1:
                    # Use a separator item
                    app_header = f"📱 {app_name}"
                    launcher_core.add_launcher_result(
                        text=app_header,
                        subtitle="",
                        index=None,
                    )

                # Add notifications for this app
                for notif in notifs:
                    self._add_notification(
                        notif, launcher_core, index if index <= 9 else None
                    )
                    index += 1
                    if index > 9:
                        break

        # Add action buttons at the bottom
        self._add_action_buttons(launcher_core)

    def _get_notifications(self, filter_type: str, search_query: str) -> List:
        """Get notifications based on filter and search query.

        Args:
            filter_type: Filter type (all, today, unread)
            search_query: Search query string

        Returns:
            List of filtered notifications
        """
        # Get notifications
        if filter_type == "unread":
            notifications = self.store.get_unread_notifications()
        elif filter_type == "today":
            # Filter by today's date
            all_notifications = self.store.get_recent_notifications(limit=500)
            today = datetime.now().date()
            notifications = [
                n for n in all_notifications if n.timestamp.date() == today
            ]
        else:
            notifications = self.store.get_recent_notifications(limit=100)

        # Apply search query if provided
        if search_query:
            notifications = [
                n
                for n in notifications
                if search_query.lower() in n.summary.lower()
                or search_query.lower() in n.body.lower()
                or search_query.lower() in n.app_name.lower()
            ]

        return notifications

    def _group_by_app(self, notifications: List) -> Dict[str, List]:
        """Group notifications by app name.

        Args:
            notifications: List of notifications

        Returns:
            Dictionary mapping app_name to list of notifications
        """
        grouped = {}
        for notif in notifications:
            app_name = notif.app_name or "Unknown"
            if app_name not in grouped:
                grouped[app_name] = []
            grouped[app_name].append(notif)
        return grouped

    def _add_header(self, text: str, launcher_core) -> None:
        """Add a header item.

        Args:
            text: Header text
            launcher_core: Launcher core reference
        """
        item_data = {"type": "header", "text": text}
        launcher_core.add_launcher_result(
            text=text,
            subtitle="",
            index=None,
            action_data=item_data,
        )

    def _add_filter_buttons(self, active_filter: str, launcher_core) -> None:
        """Add filter buttons.

        Args:
            active_filter: Currently active filter
            launcher_core: Launcher core reference
        """
        # Add filter: All
        item_data = {"type": "filter_button", "filter": "all"}
        marker = "●" if active_filter == "all" else "○"
        launcher_core.add_launcher_result(
            text=f"{marker} All Notifications",
            subtitle="Show all notifications",
            index=1,
            action_data=item_data,
        )

        # Add filter: Today
        item_data = {"type": "filter_button", "filter": "today"}
        marker = "●" if active_filter == "today" else "○"
        launcher_core.add_launcher_result(
            text=f"{marker} Today",
            subtitle="Show today's notifications",
            index=2,
            action_data=item_data,
        )

        # Add filter: Unread
        item_data = {"type": "filter_button", "filter": "unread"}
        marker = "●" if active_filter == "unread" else "○"
        launcher_core.add_launcher_result(
            text=f"{marker} Unread",
            subtitle="Show unread notifications",
            index=3,
            action_data=item_data,
        )

    def _add_notification(self, notif, launcher_core, index=None) -> None:
        """Add a notification item.

        Args:
            notif: Notification object
            launcher_core: Launcher core reference
            index: Optional index for keyboard hint
        """
        # Build subtitle
        subtitle = ""

        if notif.body:
            subtitle = truncate_text(
                notif.body, 30
            )  # Shorter truncation for simplicity

        # Just use the body without timestamp for cleaner display

        # Add read/unread indicator
        prefix = "🔵" if not notif.read else "⚪"

        # Action data
        item_data = {
            "type": "notification_item",
            "notification_id": notif.id,
            "action": "mark_read",  # Default action
        }

        launcher_core.add_launcher_result(
            text=f"{prefix} {notif.summary}",
            subtitle=subtitle,
            index=index,
            action_data=item_data,
        )

    def _add_action_buttons(self, launcher_core) -> None:
        """Add action buttons at the bottom.

        Args:
            launcher_core: Launcher core reference
        """
        # Mark all as read
        item_data = {"type": "action_button", "action": "mark_all_read"}
        launcher_core.add_launcher_result(
            text="✓ Mark All Read",
            subtitle="Mark all notifications as read",
            index=None,
            action_data=item_data,
        )

        # Clear all
        item_data = {"type": "action_button", "action": "clear_all"}
        launcher_core.add_launcher_result(
            text="✕ Clear All",
            subtitle="Delete all notifications",
            index=None,
            action_data=item_data,
        )

    # Notification management methods

    def mark_as_read(self, notification_id: str) -> None:
        """Mark a notification as read.

        Args:
            notification_id: ID of notification to mark as read
        """
        self.store.mark_as_read(notification_id)

    def dismiss(self, notification_id: str) -> None:
        """Dismiss/delete a notification.

        Args:
            notification_id: ID of notification to dismiss
        """
        self.store.remove_notification(notification_id)

    def mark_all_as_read(self) -> None:
        """Mark all notifications as read."""
        self.store.mark_all_as_read()

    def clear_all(self) -> None:
        """Clear all notifications."""
        self.store.clear_all()
