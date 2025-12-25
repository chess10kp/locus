# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from core.config import APPNAME
import gi

# No CDLL preload needed - handled by LD_PRELOAD in run.sh

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")

from gi.repository import Gtk  # pyright: ignore
from typing_extensions import final
import os
import threading
import socket
from typing import Optional

from .config import BAR_LAYOUT, MODULE_CONFIG
from .statusbar_manager import StatusbarModuleManager
from . import status_bars


@final
class StatusBar(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(
            **kwargs,
            title="statusbar",
            show_menubar=False,
            child=None,
            fullscreened=False,
            default_width=300,
            default_height=40,
            destroy_with_parent=True,
            hide_on_close=False,
            resizable=False,
            visible=True,
        )

        # Import statusbar modules to trigger registration
        import modules.statusbar  # noqa: F401

        # Import other dependencies after module registration
        from utils.utils import (
            HBox,
            get_battery_status,
            load_desktop_apps,
        )
        from utils.wm import detect_wm
        from .launcher_window import Launcher

        self.wm_client = detect_wm()
        self.launcher = Launcher(application=kwargs.get("application"))

        # Initialize module manager
        self.module_manager = StatusbarModuleManager(self)

        from .notification_store import get_notification_store

        self.notification_store = get_notification_store()

        from core.config import NOTIFICATION_DAEMON_CONFIG

        if NOTIFICATION_DAEMON_CONFIG["enabled"]:
            try:
                from core.notification_daemon import get_notification_daemon

                daemon = get_notification_daemon()
                daemon.start()

                from core.notification_queue import get_notification_queue
                from core.notification_store import Notification

                queue = get_notification_queue()

                original_add = self.notification_store.add_notification

                def add_with_banner(notif: Notification):
                    original_add(notif)
                    queue.show_notification(notif)

                self.notification_store.add_notification = add_with_banner

                print("Notification daemon started")
            except Exception as e:
                import traceback

                print(f"Error starting notification daemon: {e}")
                traceback.print_exc()

        # Styles
        self.label_style = """
             label {
                 color: #ebdbb2;
                 font-size: 10px;
                 font-weight: normal;
                 font-family: Iosevka;
                 margin: 0;
                 padding: 0;
                 transition: opacity 0.2s ease;
             }
         """
        self.sep_style = """
            label {
                color: #888888;
                font-size: 12px;
                font-weight: normal;
                font-family: monospace;
            }
        """

        self.main_box = HBox(spacing=0, hexpand=True, vexpand=True)
        self.main_box.set_halign(Gtk.Align.FILL)
        self.main_box.set_valign(Gtk.Align.FILL)
        self.main_box.set_name("main-box")
        self.set_child(self.main_box)

        # Build Layout
        self.left_box = HBox(spacing=0)
        self.middle_box = HBox(spacing=0)
        self.right_box = HBox(spacing=0)

        self.construct_modules(BAR_LAYOUT.get("left", []), self.left_box)

        # Spacers for centering middle
        left_spacer = Gtk.Label()
        left_spacer.set_hexpand(True)
        left_spacer.set_halign(Gtk.Align.FILL)

        self.construct_modules(BAR_LAYOUT.get("middle", []), self.middle_box)

        right_spacer = Gtk.Label()
        right_spacer.set_hexpand(True)
        right_spacer.set_halign(Gtk.Align.FILL)

        self.construct_modules(BAR_LAYOUT.get("right", []), self.right_box)

        # Assemble main box
        self.main_box.append(self.left_box)
        self.main_box.append(left_spacer)
        self.main_box.append(self.middle_box)
        self.main_box.append(right_spacer)
        self.main_box.append(self.right_box)

        self.apply_status_bar_styles()

        # Start IPC socket server
        self.start_ipc_server()

    def construct_modules(self, modules, box):
        """Construct modules using the plugin system and add them to the box."""
        from utils.utils import apply_styles

        for i, module_name in enumerate(modules):
            if i > 0:
                sep = Gtk.Label.new(" | ")
                apply_styles(sep, self.sep_style)
                box.append(sep)

            widget = self.create_module_widget(module_name)
            if widget:
                box.append(widget)

    def create_module_widget(self, name: str) -> Optional[Gtk.Widget]:
        """Create a widget for the given module name using the plugin system."""
        try:
            # Get module configuration
            module_config = MODULE_CONFIG.get(name, {})

            # Create module using the plugin manager
            widget = self.module_manager.create_module(name, module_config)

            if widget:
                # Special handling for modules that need WM client
                if name == "binding_mode":
                    binding_mode_instance = self.module_manager.get_module_instance(
                        name
                    )
                    if binding_mode_instance:
                        binding_mode_instance.wm_client = self.wm_client

                elif name == "workspaces":
                    workspaces_instance = self.module_manager.get_module_instance(name)
                    if workspaces_instance:
                        workspaces_instance.wm_client = self.wm_client

                return widget
            else:
                print(f"Warning: Could not create widget for module '{name}'")
                return None

        except Exception as e:
            print(f"Error creating module widget '{name}': {e}")
            # Fallback: create a simple label with error message
            error_label = Gtk.Label(label=f"[{name}]")
            error_label.set_name(f"error-{name}")
            return error_label

    def apply_status_bar_styles(self):
        """Apply the main status bar styles."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(
            """
            * {
                margin: 0;
                padding: 0;
            }

            window {
                background-color: #0e1419;
                border-bottom: 1px solid #444444;
            }

            #main-box, box {
                background-color: #0e1419;
            }

            .workspace-highlight {
                background-color: #50fa7b;
                border-radius: 2px;
            }
            """.encode()
        )
        style_context = self.get_style_context()
        style_context.add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def start_ipc_server(self):
        """Start the IPC socket server for external communication."""
        self.socket_path = "/tmp/locus_socket"
        self.ipc_running = False
        try:
            # Remove existing socket if it exists
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)

            self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server_socket.bind(self.socket_path)
            self.server_socket.listen(1)
            self.server_socket.settimeout(1)  # Non-blocking with timeout

            # Start listening in a separate thread
            self.ipc_running = True
            self.ipc_thread = threading.Thread(target=self.ipc_server_loop, daemon=True)
            self.ipc_thread.start()
        except Exception as e:
            print(f"Error starting IPC server: {e}")

    def ipc_server_loop(self):
        """IPC server loop to handle incoming connections."""
        while self.ipc_running:
            try:
                client_socket, _ = self.server_socket.accept()
                with client_socket:
                    data = client_socket.recv(1024).decode().strip()
                    if data:
                        handled = False  # Initialize handled flag
                        # Special handling for launcher command
                        if data == "launcher":
                            if self.launcher:
                                try:
                                    self.launcher.present()
                                except Exception as e:
                                    print(f"Error presenting launcher: {e}")
                            handled = True
                        elif data == "launcher:resume":
                            if self.launcher:
                                # Force resume even if config disabled
                                result = self.launcher.resume_launcher()
                                # If resume failed (no state), still show the launcher
                                if not result:
                                    try:
                                        self.launcher.present()
                                    except Exception as e:
                                        print(f"Error presenting launcher: {e}")
                            handled = True
                        elif data == "launcher:fresh":
                            if self.launcher:
                                # Force fresh start - clear state and show empty
                                self.launcher.launcher_state.clear_state()
                                self.launcher.show_launcher()
                            handled = True
                        elif data.startswith("launcher dmenu:"):
                            # Handle dmenu with options
                            if self.launcher:
                                options = data[14:]  # Remove "launcher dmenu:" prefix
                                dmenu_launcher = self.launcher.launcher_registry.get_launcher_by_trigger(
                                    "dmenu"
                                )
                                if dmenu_launcher:
                                    dmenu_launcher.set_options(options)
                                    self.launcher.search_entry.set_text(">dmenu")
                                    try:
                                        self.launcher.present()
                                    except Exception as e:
                                        print(f"Error presenting launcher: {e}")
                                    self.launcher.on_entry_activate(
                                        self.launcher.search_entry
                                    )
                            handled = True
                        elif data.startswith(">") or data.startswith("launcher "):
                            # Send launcher commands to the launcher
                            if self.launcher:
                                # Extract the command if it starts with "launcher "
                                if data.startswith("launcher "):
                                    command = data[8:]  # Remove "launcher " prefix
                                    self.launcher.search_entry.set_text(command)
                                    try:
                                        self.launcher.present()
                                    except Exception as e:
                                        print(f"Error presenting launcher: {e}")
                                    self.launcher.on_entry_activate(
                                        self.launcher.search_entry
                                    )
                                else:
                                    # Direct command starting with >
                                    self.launcher.search_entry.set_text(data)
                                    try:
                                        self.launcher.present()
                                    except Exception as e:
                                        print(f"Error presenting launcher: {e}")
                                    self.launcher.on_entry_activate(
                                        self.launcher.search_entry
                                    )
                            handled = True
                        else:
                            # Handle the message through all module managers
                            handled = False
                            for sb in status_bars:
                                if sb.module_manager.handle_ipc_message(data):
                                    handled = True
                        if not handled:
                            print(f"Unhandled IPC message: {data}")
            except socket.timeout:
                continue
            except OSError:
                # Socket was closed
                break
            except Exception as e:
                print(f"IPC server error: {e}")

    def send_status_message(self, message: str):
        """Send a status message to the custom message module."""
        self.module_manager.handle_ipc_message(f"status:{message}")

    def on_launcher_clicked(self, button):
        """Handle launcher button click."""
        try:
            self.launcher.present()
        except Exception as e:
            print(f"Error presenting launcher: {e}")

    def cleanup(self):
        """Clean up resources when the statusbar is destroyed."""
        if hasattr(self, "ipc_running"):
            self.ipc_running = False

        from core.notification_queue import get_notification_queue

        try:
            queue = get_notification_queue()
            queue.cleanup()
        except Exception:
            pass

        from core.notification_daemon import get_notification_daemon

        try:
            daemon = get_notification_daemon()
            daemon.stop()
        except Exception:
            pass

        if hasattr(self, "module_manager"):
            self.module_manager.cleanup()

        if hasattr(self, "server_socket"):
            self.server_socket.close()

        if hasattr(self, "ipc_thread") and self.ipc_thread.is_alive():
            self.ipc_thread.join(timeout=2.0)

        if hasattr(self, "socket_path") and os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
