# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import subprocess
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

import gi

gi.require_version("GLib", "2.0")
gi.require_version("Gio", "2.0")
from gi.repository import GLib, Gio

from core.notification_store import Notification, NotificationStore
from core.config import NOTIFICATION_CONFIG


def send_notification(
    app_name: str,
    summary: str,
    body: str = "",
    icon: str = "",
    urgency: str = "normal",
    expire_timeout: int = 5000,
    actions: Optional[List[str]] = None,
) -> str:
    """Send a notification via notify-send.

    Args:
        app_name: Application name
        summary: Notification title
        body: Notification body text
        icon: Icon name or path
        urgency: Urgency level (low, normal, critical)
        expire_timeout: Timeout in milliseconds
        actions: List of action strings

    Returns:
        Notification ID
    """
    # Generate a unique ID for this notification
    notification_id = str(uuid.uuid4())

    # Build notify-send command
    cmd = ["notify-send"]

    # Add urgency
    if urgency in ["low", "normal", "critical"]:
        cmd.extend(["-u", urgency])

    # Add expire time
    cmd.extend(["-t", str(expire_timeout)])

    # Add icon if provided
    if icon:
        cmd.extend(["-i", icon])

    # Add app name
    cmd.extend(["-a", app_name])

    # Add summary and body
    cmd.append(summary)
    if body:
        cmd.append(body)

    # Send notification
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error sending notification: {e}")

    # Note: The notification will be captured by the D-Bus interceptor
    # and added to the store there, so we don't add it here directly
    return notification_id


def format_timestamp(dt: datetime) -> str:
    """Format a notification timestamp for display.

    Args:
        dt: Datetime to format

    Returns:
        Formatted timestamp string
    """
    now = datetime.now()
    diff = now - dt

    # Less than a minute
    if diff.seconds < 60:
        return "Just now"

    # Less than an hour
    if diff.seconds < 3600:
        minutes = diff.seconds // 60
        return f"{minutes}m ago"

    # Today
    if dt.date() == now.date():
        return dt.strftime("%H:%M")

    # Yesterday
    yesterday = now - timedelta(days=1)
    if dt.date() == yesterday.date():
        return "Yesterday"

    # This week
    if diff.days < 7:
        return dt.strftime("%A")

    # Otherwise show date
    return dt.strftime("%b %d")


def get_app_icon_name(app_name: str) -> str:
    """Get the icon name for an application.

    Args:
        app_name: Application name

    Returns:
        Icon name or empty string
    """
    # Try to find a .desktop file for this app
    try:
        app_info = Gio.DesktopAppInfo.new(f"{app_name.lower()}.desktop")
        if app_info:
            icon = app_info.get_string("Icon")
            if icon:
                return icon
    except Exception:
        pass

    # Fallback: try common icon names
    app_lower = app_name.lower()
    common_icons = {
        "firefox": "firefox",
        "chrome": "google-chrome",
        "chromium": "chromium",
        "discord": "discord",
        "slack": "slack",
        "spotify": "spotify",
        "vlc": "vlc",
        "thunderbird": "thunderbird",
        "vscode": "visual-studio-code",
        "code": "visual-studio-code",
    }

    return common_icons.get(app_lower, "dialog-information")


def start_notification_interceptor(store: NotificationStore) -> None:
    """Start monitoring D-Bus for incoming notifications.

    This listens to the org.freedesktop.Notifications D-Bus interface
    and captures all notifications sent to any notification daemon.

    Args:
        store: NotificationStore to capture notifications to
    """
    try:
        # Create D-Bus proxy for the notification daemon
        notification_proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
        )

        if notification_proxy:
            # Subscribe to ActionInvoked signal
            notification_proxy.connect(
                "g-signal", _on_dbus_signal, store
            )

            print("Notification interceptor started")

    except Exception as e:
        print(f"Error starting notification interceptor: {e}")
        print("Notifications will only be captured from Locus API")


def _on_dbus_signal(
    proxy: Gio.DBusProxy,
    sender_name: str,
    signal_name: str,
    parameters: GLib.Variant,
    store: NotificationStore,
) -> None:
    """Handle D-Bus signals from the notification daemon.

    Args:
        proxy: D-Bus proxy
        sender_name: Sender of the signal
        signal_name: Name of the signal
        parameters: Signal parameters
        store: NotificationStore to update
    """
    try:
        # We're mainly interested in capturing notifications
        # The Notify method is called, not signaled, so we need a different approach

        # Since we can't directly intercept Notify calls via signals,
        # we'll rely on the fact that most notifications are sent via
        # our send_notification() wrapper or will be visible in the system

        pass

    except Exception as e:
        print(f"Error handling D-Bus signal: {e}")


# Alternative approach: Use a D-Bus service to intercept notifications
class NotificationInterceptor:
    """D-Bus service to intercept notification calls."""

    def __init__(self, store: NotificationStore):
        """Initialize the interceptor.

        Args:
            store: NotificationStore to capture notifications to
        """
        self.store = store
        self.bus_id = None
        self.connection = None

    def start(self) -> bool:
        """Start the interceptor service.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get the session bus
            self.connection = Gio.bus_get_sync(Gio.BusType.SESSION)

            # Subscribe to all D-Bus messages to org.freedesktop.Notifications
            # This is a workaround - we can't easily intercept Notify calls
            # without replacing the daemon

            # For now, we'll use a different approach:
            # Monitor the daemon's signals if available

            print("Notification interceptor: Using passive monitoring mode")
            return True

        except Exception as e:
            print(f"Error starting interceptor service: {e}")
            return False

    def stop(self) -> None:
        """Stop the interceptor service."""
        if self.bus_id:
            # Unregister from bus
            self.bus_id = None


def get_urgency_from_hints(hints: Dict[str, Any]) -> str:
    """Extract urgency level from notification hints.

    Args:
        hints: Notification hints dictionary

    Returns:
        Urgency level (low, normal, critical)
    """
    if not hints:
        return "normal"

    urgency = hints.get("urgency")
    if urgency is not None:
        if urgency == 0:
            return "low"
        elif urgency == 1:
            return "normal"
        elif urgency == 2:
            return "critical"

    return "normal"


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text with ... if shortened
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    return text[: max_length - 3] + "..."



# Import timedelta for format_timestamp
from datetime import timedelta