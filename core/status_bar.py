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
        from .launcher import Launcher

        self.wm_client = detect_wm()
        self.launcher = Launcher(application=kwargs.get("application"))

        # Initialize module manager
        self.module_manager = StatusbarModuleManager(self)

        # Styles
        self.label_style = """
            label {
                color: #ebdbb2;
                font-size: 20px;
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

        self.main_box = HBox(spacing=0, hexpand=True)
        self.set_child(self.main_box)

        # Build Layout
        self.left_box = HBox(spacing=0)
        self.middle_box = HBox(spacing=0)
        self.right_box = HBox(spacing=0)

        self.construct_modules(BAR_LAYOUT.get("left", []), self.left_box)

        # Spacers for centering middle
        left_spacer = Gtk.Label()
        left_spacer.set_hexpand(True)

        self.construct_modules(BAR_LAYOUT.get("middle", []), self.middle_box)

        right_spacer = Gtk.Label()
        right_spacer.set_hexpand(True)

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
            window {
                background-color: #0e1419;
                border-bottom: 1px solid #444444;
            }

            .workspace-highlight {
                background-color: #50fa7b;
                margin: 0;
                padding: 0;
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
                        # Special handling for launcher command
                        if data == "launcher":
                            if self.launcher:
                                self.launcher.present()
                            handled = True
                        else:
                            # Handle the message through the module manager
                            handled = self.module_manager.handle_ipc_message(data)
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
        self.launcher.present()

    def cleanup(self):
        """Clean up resources when the statusbar is destroyed."""
        # Stop IPC thread first
        if hasattr(self, "ipc_running"):
            self.ipc_running = False

        if hasattr(self, "module_manager"):
            self.module_manager.cleanup()

        if hasattr(self, "server_socket"):
            self.server_socket.close()

        # Wait for IPC thread to finish (with timeout)
        if hasattr(self, "ipc_thread") and self.ipc_thread.is_alive():
            self.ipc_thread.join(timeout=2.0)

        if hasattr(self, "socket_path") and os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
