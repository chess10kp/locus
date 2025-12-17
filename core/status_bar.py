# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from gi.repository import GLib, Gtk  # pyright: ignore
from typing_extensions import final
import os
import subprocess
import json
import threading
import socket

from datetime import datetime as dt

from utils.utils import apply_styles, HBox, get_battery_status, load_desktop_apps
from utils.wm import detect_wm
from .launcher import Launcher
from .config import BAR_LAYOUT


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

        self.wm_client = detect_wm()
        self.launcher = Launcher(application=kwargs.get("application"))

        # Initialize module references to None
        self.launcher_button = None
        self.fixed = None
        self.workspaces_container = None
        self.highlight_indicator = None
        self.binding_state_label = None
        self.emacs_clock_label = None
        self.time_label = None
        self.battery_label = None
        self.custom_message_label = None
        self.workspace_widgets = {}

        # Styles
        self.label_style = """
            label {
                color: #ebdbb2;
                font-size: 18px;
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

        # Start event listener
        if self.fixed:  # Only if workspaces module exists
            self.wm_client.start_event_listener(self.update_workspaces)

        # Start update loops
        all_modules = (
            BAR_LAYOUT.get("left", [])
            + BAR_LAYOUT.get("middle", [])
            + BAR_LAYOUT.get("right", [])
        )
        if "time" in all_modules:
            self.update_time()
            GLib.timeout_add_seconds(60, self.update_time_callback)

        if "battery" in all_modules:
            self.update_battery()
            GLib.timeout_add_seconds(60, self.update_battery_callback)

        if "binding_mode" in all_modules:
            self.update_binding_state()
            GLib.timeout_add_seconds(1, self.update_binding_state_callback)

        if "emacs_clock" in all_modules:
            self.update_emacs_clock()
            GLib.timeout_add_seconds(10, self.update_emacs_clock_callback)

        if "workspaces" in all_modules:
            self.update_workspaces()

        # Start IPC socket server always, as it might be used for launcher or custom messages
        self.start_ipc_server()

    def construct_modules(self, modules, box):
        """Construct modules and add them to the box."""
        for i, module_name in enumerate(modules):
            if i > 0:
                sep = Gtk.Label.new(" | ")
                apply_styles(sep, self.sep_style)
                box.append(sep)

            widget = self.create_module_widget(module_name)
            if widget:
                box.append(widget)

    def create_module_widget(self, name):
        """Create a widget for the given module name."""
        if name == "launcher":
            self.launcher_button = Gtk.Button(label="󰀻")
            self.launcher_button.connect("clicked", self.on_launcher_clicked)
            apply_styles(
                self.launcher_button,
                """
                button {
                    background: transparent;
                    color: #ebdbb2;
                    border: none;
                    font-size: 18px;
                    font-family: Iosevka;
                    margin: 0;
                    padding: 0;
                }
                button:hover {
                    background: #1a1a1a;
                }
            """,
            )
            return self.launcher_button

        elif name == "workspaces":
            self.fixed = Gtk.Fixed()

            # Highlight indicator
            self.highlight_indicator = Gtk.Label(label="")
            self.highlight_indicator.get_style_context().add_class(
                "workspace-highlight"
            )
            apply_styles(
                self.highlight_indicator,
                """
                label {
                    background-color: #ebdbb2;
                    margin: 0;
                    padding: 0;
                    border-radius: 2px;
                }
                """,
            )
            self.fixed.put(self.highlight_indicator, 0, 0)

            # Workspace text container
            self.workspaces_container = HBox(spacing=0)
            self.fixed.put(self.workspaces_container, 0, 0)

            return self.fixed

        elif name == "binding_mode":
            self.binding_state_label = Gtk.Label()
            apply_styles(self.binding_state_label, self.label_style)
            return self.binding_state_label

        elif name == "emacs_clock":
            self.emacs_clock_label = Gtk.Label()
            apply_styles(self.emacs_clock_label, self.label_style)
            return self.emacs_clock_label

        elif name == "time":
            self.time_label = Gtk.Label()
            apply_styles(self.time_label, self.label_style)
            return self.time_label

        elif name == "battery":
            self.battery_label = Gtk.Label()
            apply_styles(self.battery_label, self.label_style)
            return self.battery_label

        elif name == "custom_message":
            self.custom_message_label = Gtk.Label()
            apply_styles(self.custom_message_label, self.label_style)
            return self.custom_message_label

        return None

    def update_time(self):
        """Update time display"""
        if self.time_label:
            current_time = dt.now().strftime("%H:%M")
            self.time_label.set_text(current_time)

    def update_battery(self):
        """Update battery display"""
        if self.battery_label:
            battery_status = get_battery_status()
            self.battery_label.set_text(battery_status)

    def animate_highlight(self, start_x, end_x, start_w, end_w, step=0, total_steps=10):
        """Animate sliding the workspace highlight"""
        if step < total_steps:
            progress = (step + 1) / total_steps
            x = start_x + (end_x - start_x) * progress
            w = start_w + (end_w - start_w) * progress

            self.fixed.move(self.highlight_indicator, int(x), 0)
            self.highlight_indicator.set_size_request(int(w), 26)

            GLib.timeout_add(
                10,
                self.animate_highlight,
                start_x,
                end_x,
                start_w,
                end_w,
                step + 1,
                total_steps,
            )
        else:
            self.fixed.move(self.highlight_indicator, int(end_x), 0)
            self.highlight_indicator.set_size_request(int(end_w), 26)
        return False

    def update_highlight_position(self, active_name):
        """Update position of the highlight widget based on active workspace"""
        if active_name is None or active_name not in self.workspace_widgets:
            self.highlight_indicator.set_visible(False)
            return

        target_widget = self.workspace_widgets[active_name]
        allocation = target_widget.get_allocation()

        # If allocation is not ready yet (e.g. initial load), retry shortly
        if allocation.width <= 1:
            GLib.timeout_add(50, self.update_highlight_position, active_name)
            return False

        target_x = allocation.x
        target_w = allocation.width

        start_x = getattr(self, "current_highlight_x", target_x)
        start_w = getattr(self, "current_highlight_w", target_w)

        # Determine if we should animate
        should_animate = (
            start_x != target_x or start_w != target_w
        ) and self.highlight_indicator.get_visible()

        self.highlight_indicator.set_visible(True)
        self.current_highlight_x = target_x
        self.current_highlight_w = target_w

        if should_animate:
            self.animate_highlight(start_x, target_x, start_w, target_w)
        else:
            self.fixed.move(self.highlight_indicator, int(target_x), 0)
            self.highlight_indicator.set_size_request(int(target_w), 26)

        return False

    def update_workspaces(self):
        """Update workspaces display"""
        if not self.workspaces_container:
            return

        try:
            workspaces = self.wm_client.get_workspaces()
            ws_sorted = sorted(workspaces, key=lambda ws: (ws.num, ws.name))

            current_focused = next((ws for ws in ws_sorted if ws.focused), None)

            # Recreate workspace widgets only if necessary
            # For simplicity, we'll recreate if the list of workspaces changed
            # In a more complex app, we'd diff.
            current_names = [ws.name for ws in ws_sorted]
            existing_names_list = list(self.workspace_widgets.keys())

            if current_names != existing_names_list:
                # Clear existing
                child = self.workspaces_container.get_first_child()
                while child:
                    next_child = child.get_next_sibling()
                    self.workspaces_container.remove(child)
                    child = next_child
                self.workspace_widgets.clear()

                # Create new
                for ws in ws_sorted:
                    label = Gtk.Label(label=f" {ws.name} ")
                    apply_styles(label, self.label_style)
                    self.workspaces_container.append(label)
                    self.workspace_widgets[ws.name] = label

            # Update styles for focus
            for ws in ws_sorted:
                widget = self.workspace_widgets.get(ws.name)
                if widget:
                    if ws.focused:  # simplified check since we iterate ws_sorted
                        widget.set_markup(
                            f'<span foreground="#0e1419"> {ws.name} </span>'
                        )
                    else:
                        widget.set_markup(
                            f'<span foreground="#ebdbb2"> {ws.name} </span>'
                        )

            # Trigger highlight update
            GLib.idle_add(
                self.update_highlight_position,
                current_focused.name if current_focused else None,
            )

        except Exception as e:
            print(f"Error updating workspaces: {e}")

    def update_binding_state(self):
        """Update binding state display"""
        if not self.binding_state_label:
            return

        try:
            result = subprocess.run(
                ["swaymsg", "-t", "get_binding_state"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                mode = data.get("name", "default")
                if mode != "default":
                    self.binding_state_label.set_text(f"[{mode}]")
                else:
                    self.binding_state_label.set_text("")
            else:
                self.binding_state_label.set_text("")
        except Exception:
            self.binding_state_label.set_text("")

    def update_emacs_clock(self):
        """Update Emacs clocked task display"""
        if not self.emacs_clock_label:
            return

        try:
            result = subprocess.run(
                [
                    "emacsclient",
                    "-e",
                    '(progn (require \'org-clock) (if (org-clocking-p) org-clock-heading ""))',
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                task = result.stdout.strip().strip('"')  # Remove quotes if any
                self.emacs_clock_label.set_text(task)
            else:
                self.emacs_clock_label.set_text("")
        except Exception:
            self.emacs_clock_label.set_text("")

    def update_time_callback(self) -> bool:
        """Callback for time updates"""
        self.update_time()
        return True

    def update_battery_callback(self) -> bool:
        """Callback for battery updates"""
        self.update_battery()
        return True

    def update_binding_state_callback(self) -> bool:
        """Callback for binding state updates"""
        self.update_binding_state()
        return True

    def update_emacs_clock_callback(self) -> bool:
        """Callback for Emacs clock updates"""
        self.update_emacs_clock()
        return True

    def update_custom_message(self, message: str):
        """Update custom message display"""
        if self.custom_message_label:
            self.custom_message_label.set_text(message)

    def on_launcher_clicked(self, button):
        self.launcher.show_launcher()

    def start_ipc_server(self):
        """Start Unix socket server for IPC"""
        from .config import SOCKET_PATH

        def server_loop():
            # Remove socket if exists
            try:
                os.unlink(SOCKET_PATH)
            except OSError:
                pass

            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(SOCKET_PATH)
            server.listen(1)

            while True:
                try:
                    conn, _ = server.accept()
                    data = conn.recv(1024)
                    if data:
                        message = data.decode("utf-8").strip()
                        if message == "launcher":
                            GLib.idle_add(self.launcher.show_launcher)
                        elif message.startswith("launcher "):
                            app_name = message[9:].strip()
                            # Launch the app
                            apps = load_desktop_apps()
                            for app in apps:
                                if app_name.lower() in app["name"].lower():
                                    try:
                                        subprocess.Popen([app["exec"]], shell=False)
                                    except Exception as e:
                                        print(f"Failed to launch {app['name']}: {e}")
                                    break
                            else:
                                print(f"App '{app_name}' not found")
                        else:
                            GLib.idle_add(self.update_custom_message, message)
                    conn.close()
                except Exception as e:
                    print(f"IPC error: {e}")
                    break

            server.close()

        thread = threading.Thread(target=server_loop)
        thread.daemon = True
        thread.start()

    def apply_status_bar_styles(self):
        """Apply CSS styling to the status bar like Emacs modeline"""
        apply_styles(
            self,
            """
            window {
                background: #0e1418;
                margin: 0;
                padding: 0;
            }
        """,
        )

        apply_styles(
            self.main_box,
            """
            box {
                background: transparent;
                padding: 0;
                margin: 0;
            }
        """,
        )

        apply_styles(
            self.left_box,
            """
            box {
                padding: 0;
                margin: 0;
            }
        """,
        )

        apply_styles(
            self.right_box,
            """
            box {
                padding: 0;
                margin: 0;
            }
        """,
        )
