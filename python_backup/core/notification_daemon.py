# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore
# ruff: noqa: E402


import uuid
from datetime import datetime
from typing import Optional, Dict

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")

from gi.repository import Gio, GLib

from core.notification_store import Notification, get_notification_store


class NotificationDaemon:
    """D-Bus notification daemon implementing org.freedesktop.Notifications."""

    _instance: Optional["NotificationDaemon"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self.store = get_notification_store()
        self.next_id: int = 1
        self.active_notifications: Dict[int, str] = {}
        self.connection = None
        self.bus_id = None
        self.name_id = None
        self._initialized = True

    def start(self) -> bool:
        """Start the D-Bus notification service."""

        try:
            self.connection = Gio.bus_get_sync(Gio.BusType.SESSION)

            introspection_data = Gio.DBusNodeInfo.new_for_xml(
                """
            <node>
                <interface name="org.freedesktop.Notifications">
                    <method name="Notify">
                        <arg type="s" name="app_name" direction="in"/>
                        <arg type="u" name="replaces_id" direction="in"/>
                        <arg type="s" name="app_icon" direction="in"/>
                        <arg type="s" name="summary" direction="in"/>
                        <arg type="s" name="body" direction="in"/>
                        <arg type="as" name="actions" direction="in"/>
                        <arg type="a{sv}" name="hints" direction="in"/>
                        <arg type="i" name="expire_timeout" direction="in"/>
                        <arg type="u" name="id" direction="out"/>
                    </method>
                    <method name="CloseNotification">
                        <arg type="u" name="id" direction="in"/>
                    </method>
                    <method name="GetCapabilities">
                        <arg type="as" name="capabilities" direction="out"/>
                    </method>
                    <method name="GetServerInformation">
                        <arg type="s" name="name" direction="out"/>
                        <arg type="s" name="vendor" direction="out"/>
                        <arg type="s" name="version" direction="out"/>
                        <arg type="s" name="spec_version" direction="out"/>
                    </method>
                    <method name="TestMethod">
                        <arg type="s" name="input" direction="in"/>
                        <arg type="s" name="output" direction="out"/>
                    </method>
                    <signal name="NotificationClosed">
                        <arg type="u" name="id"/>
                        <arg type="u" name="reason"/>
                    </signal>
                    <signal name="ActionInvoked">
                        <arg type="u" name="id"/>
                        <arg type="s" name="action_key"/>
                    </signal>
                </interface>
            </node>
            """
            )

            interface_info = introspection_data.interfaces[0]
            interface_info = introspection_data.interfaces[0]

            self.bus_id = self.connection.register_object(
                "/org/freedesktop/Notifications",
                interface_info,
                self._method_call,
                None,
                None,
            )

            if self.bus_id == 0:
                raise Exception("Failed to register D-Bus object")

            self.name_id = Gio.bus_own_name_on_connection(
                self.connection,
                "org.freedesktop.Notifications",
                Gio.BusNameOwnerFlags.ALLOW_REPLACEMENT | Gio.BusNameOwnerFlags.REPLACE,
                self._on_name_acquired,
                self._on_name_lost,
            )

            if self.name_id == 0:
                raise Exception("Failed to own D-Bus name")

            print("Notification daemon started")
            return True

        except Exception as e:
            print(f"Error starting notification daemon: {e}")
            return False

    def stop(self) -> None:
        """Stop the D-Bus notification service."""
        if self.bus_id and self.connection:
            self.connection.unregister_object(self.bus_id)
            self.bus_id = None
        if self.name_id and self.connection:
            self.connection.unown_name(self.name_id)
            self.name_id = None

    def _method_call(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        """Handle D-Bus method calls."""
        try:
            if interface_name == "org.freedesktop.Notifications":
                if method_name == "Notify":
                    self._handle_notify(parameters, invocation)
                elif method_name == "CloseNotification":
                    self._handle_close_notification(parameters, invocation)
                elif method_name == "GetCapabilities":
                    self._handle_get_capabilities(invocation)
                elif method_name == "GetServerInformation":
                    self._handle_get_server_information(invocation)
                elif method_name == "TestMethod":
                    self._handle_test_method(parameters, invocation)
                else:
                    invocation.return_dbus_error(
                        "org.freedesktop.DBus.Error.UnknownMethod",
                        f"Unknown method {method_name}",
                    )
            else:
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownInterface",
                    f"Unknown interface {interface_name}",
                )
        except Exception as e:
            print(f"Error handling method {method_name}: {e}")
            invocation.return_dbus_error("org.freedesktop.Notifications.Error", str(e))

    def _handle_notify(
        self, parameters: GLib.Variant, invocation: Gio.DBusMethodInvocation
    ) -> None:
        """Handle Notify method call."""
        try:
            (
                app_name,
                replaces_id,
                app_icon,
                summary,
                body,
                actions,
                hints,
                expire_timeout,
            ) = parameters.unpack()

            # Create notification
            if replaces_id > 0:
                notif_id = replaces_id
            else:
                notif_id = self.next_id
                self.next_id += 1

            notif = Notification(
                id=str(uuid.uuid4()),
                app_name=app_name or "Unknown",
                app_icon=app_icon or "",
                summary=summary or "",
                body=body or "",
                actions=list(actions),
                hints=dict(hints),
                timestamp=datetime.now(),
                expire_timeout=expire_timeout,
            )

            self.active_notifications[notif_id] = notif.id
            self.store.add_notification(notif)

            # Show banner
            from core.notification_queue import get_notification_queue

            queue = get_notification_queue()
            queue.show_notification(notif)

            invocation.return_value(GLib.Variant("(u)", (notif_id,)))
        except Exception as e:
            print(f"Error in Notify: {e}")
            import traceback

            traceback.print_exc()
            invocation.return_dbus_error("org.freedesktop.Notifications.Error", str(e))

        if replaces_id > 0:
            notif_id = replaces_id
        else:
            notif_id = self.next_id
            self.next_id += 1

        urgency = hints.get("urgency", 1)
        if urgency == 0:
            urgency_str = "low"
        elif urgency == 2:
            urgency_str = "critical"
        else:
            urgency_str = "normal"

        actions_list = list(actions)

        if expire_timeout == -1 or urgency_str == "critical":
            final_timeout = -1
        elif expire_timeout == 0:
            final_timeout = 5000
        else:
            final_timeout = expire_timeout

        notif = Notification(
            id=str(uuid.uuid4()),
            app_name=app_name or "Unknown",
            app_icon=app_icon or "",
            summary=summary or "",
            body=body or "",
            actions=actions_list,
            hints=dict(hints),
            timestamp=datetime.now(),
            expire_timeout=final_timeout,
        )

        try:
            unpacked = parameters.unpack()
            print(f"Unpacked: {len(unpacked)} items")
            (
                app_name,
                replaces_id,
                app_icon,
                summary,
                body,
                actions,
                hints,
                expire_timeout,
            ) = unpacked
            print(f"Notify: {app_name} - {summary}")

            invocation.return_value(GLib.Variant("(u)", (42,)))
        except Exception as e:
            print(f"Error in Notify: {e}")
            import traceback

            traceback.print_exc()
            invocation.return_dbus_error("org.freedesktop.Notifications.Error", str(e))

    def _handle_close_notification(
        self, parameters: GLib.Variant, invocation: Gio.DBusMethodInvocation
    ) -> None:
        """Handle CloseNotification method call."""
        notif_id = parameters.unpack()[0]

        if notif_id in self.active_notifications:
            store_id = self.active_notifications.pop(notif_id)
            self.store.remove_notification(store_id)

        invocation.return_value(GLib.Variant("()"))

    def _handle_get_capabilities(self, invocation: Gio.DBusMethodInvocation) -> None:
        """Handle GetCapabilities method call."""
        capabilities = [
            "actions",
            "body",
            "body-hyperlinks",
            "body-markup",
            "icon-static",
            "persistence",
            "sound",
        ]
        invocation.return_value(GLib.Variant("(as)", (capabilities,)))

    def _handle_get_server_information(
        self, invocation: Gio.DBusMethodInvocation
    ) -> None:
        """Handle GetServerInformation method call."""
        invocation.return_value(
            GLib.Variant("(ssss)", ("Locus Notification Daemon", "Locus", "1.0", "1.2"))
        )

    def _handle_test_method(
        self, parameters: GLib.Variant, invocation: Gio.DBusMethodInvocation
    ) -> None:
        """Handle TestMethod method call."""
        input_str = parameters.unpack()[0]
        invocation.return_value(GLib.Variant("(s)", (f"Echo: {input_str}",)))

    def _on_name_acquired(self, connection: Gio.DBusConnection, name: str) -> None:
        """Called when D-Bus name is acquired."""
        print(f"Notification daemon: acquired name '{name}'")

    def _on_name_lost(self, connection: Gio.DBusConnection, name: str) -> None:
        """Called when D-Bus name is lost."""
        import traceback

        print(f"Notification daemon: lost name '{name}'")
        print(f"Connection still active: {self.connection is not None}")
        print(f"Bus ID still set: {self.bus_id is not None}")
        traceback.print_exc()

    def emit_notification_closed(self, notif_id: int, reason: int) -> None:
        """Emit NotificationClosed signal."""
        if self.connection:
            self.connection.emit_signal(
                None,
                "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications",
                "NotificationClosed",
                GLib.Variant("(uu)", (notif_id, reason)),
            )

    def emit_action_invoked(self, notif_id: int, action_key: str) -> None:
        """Emit ActionInvoked signal."""
        if self.connection:
            self.connection.emit_signal(
                None,
                "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications",
                "ActionInvoked",
                GLib.Variant("(us)", (notif_id, action_key)),
            )


_notification_daemon_instance: Optional[NotificationDaemon] = None


def get_notification_daemon() -> NotificationDaemon:
    """Get the singleton notification daemon instance."""
    global _notification_daemon_instance
    if _notification_daemon_instance is None:
        _notification_daemon_instance = NotificationDaemon()
    return _notification_daemon_instance
