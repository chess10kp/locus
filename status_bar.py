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

from utils import apply_styles, HBox, get_battery_status, load_desktop_apps
from wm import detect_wm
from launcher import Launcher


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

        self.main_box = HBox(spacing=0, hexpand=True)
        self.set_child(self.main_box)

        self.left_box = HBox(spacing=0)
        self.launcher_button = Gtk.Button(label="󰀻")
        self.launcher_button.connect("clicked", self.on_launcher_clicked)
        self.sep_launcher = Gtk.Label.new(" | ")
        self.fixed = Gtk.Fixed()
        self.workspaces_label = Gtk.Label()
        self.fixed.put(self.workspaces_label, 0, 0)
        self.sep_left = Gtk.Label.new(" | ")
        self.binding_state_label = Gtk.Label()
        self.sep_emacs = Gtk.Label.new(" | ")
        self.emacs_clock_label = Gtk.Label()

        # Create right section: time | battery | custom_message
        self.right_box = HBox(spacing=0)
        self.time_label = Gtk.Label()
        self.sep_right = Gtk.Label.new(" | ")
        self.battery_label = Gtk.Label()
        self.sep_custom = Gtk.Label.new(" | ")
        self.custom_message_label = Gtk.Label()

        self.previous_focused = None
        self.update_time()
        self.update_battery()
        self.update_workspaces()
        self.update_binding_state()
        self.update_emacs_clock()

        # Add to left box
        self.left_box.append(self.launcher_button)
        self.left_box.append(self.sep_launcher)
        self.left_box.append(self.fixed)
        self.left_box.append(self.sep_left)
        self.left_box.append(self.binding_state_label)
        self.left_box.append(self.sep_emacs)
        self.left_box.append(self.emacs_clock_label)

        # Add to right box
        self.right_box.append(self.time_label)
        self.right_box.append(self.sep_right)
        self.right_box.append(self.battery_label)
        self.right_box.append(self.sep_custom)
        self.right_box.append(self.custom_message_label)

        # Add to main box: left, spacer, right
        self.main_box.append(self.left_box)
        spacer = Gtk.Label()
        spacer.set_hexpand(True)
        self.main_box.append(spacer)
        self.main_box.append(self.right_box)

        self.apply_status_bar_styles()

        # Start event listener
        self.wm_client.start_event_listener(self.update_workspaces)

        GLib.timeout_add_seconds(60, self.update_time_callback)
        GLib.timeout_add_seconds(60, self.update_battery_callback)
        GLib.timeout_add_seconds(1, self.update_binding_state_callback)
        GLib.timeout_add_seconds(10, self.update_emacs_clock_callback)

        # Start IPC socket server
        self.start_ipc_server()

    def update_time(self):
        """Update time display"""
        current_time = dt.now().strftime("%H:%M")
        self.time_label.set_text(current_time)

    def update_battery(self):
        """Update battery display"""
        battery_status = get_battery_status()
        self.battery_label.set_text(battery_status)

    def animate_slide(self, start_x, end_x, step=0, total_steps=10):
        """Animate sliding the workspace label"""
        if step < total_steps:
            x = start_x + (end_x - start_x) * (step + 1) / total_steps
            self.fixed.move(self.workspaces_label, x, 0)
            GLib.timeout_add(
                20, self.animate_slide, start_x, end_x, step + 1, total_steps
            )
        else:
            self.fixed.move(self.workspaces_label, end_x, 0)
        return False

    def update_workspaces(self):
        """Update workspaces display with slide transition"""
        try:
            workspaces = self.wm_client.get_workspaces()
            ws_sorted = sorted(
                workspaces,
                key=lambda ws: (
                    ws.num,
                    ws.name,
                ),
            )
            current_focused = next((ws for ws in ws_sorted if ws.focused), None)
            current_num = current_focused.num if current_focused else 0

            # Determine slide direction
            direction = 0
            if self.previous_focused is not None:
                if current_num > self.previous_focused:
                    direction = -50  # Slide from right
                elif current_num < self.previous_focused:
                    direction = 50  # Slide from left

            self.previous_focused = current_num

            # Update text
            text_parts = []
            for ws in ws_sorted:
                name = ws.name
                if ws.focused:
                    name = (
                        f'<span background="#ebdbb2" foreground="#0e1419">{name}</span>'
                    )
                text_parts.append(name)
            self.workspaces_label.set_markup(" ".join(text_parts))

            # Animate slide
            if direction != 0:
                self.animate_slide(direction, 0)
            else:
                self.fixed.move(self.workspaces_label, 0, 0)
        except Exception:
            self.workspaces_label.set_text("?")
            self.fixed.move(self.workspaces_label, 0, 0)

    def update_binding_state(self):
        """Update binding state display"""
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
        self.custom_message_label.set_text(message)

    def on_launcher_clicked(self, button):
        self.launcher.show_launcher()

    def start_ipc_server(self):
        """Start Unix socket server for IPC"""
        SOCKET_PATH = "/tmp/locus_socket"

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

        label_style = """
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

        sep_style = """
            label {
                color: #888888;
                font-size: 12px;
                font-weight: normal;
                font-family: monospace;
            }
        """

        apply_styles(self.time_label, label_style)
        apply_styles(self.battery_label, label_style)
        apply_styles(self.workspaces_label, label_style)
        apply_styles(self.binding_state_label, label_style)
        apply_styles(self.emacs_clock_label, label_style)
        apply_styles(self.custom_message_label, label_style)
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
        apply_styles(self.sep_left, sep_style)
        apply_styles(self.sep_right, sep_style)
        apply_styles(self.sep_emacs, sep_style)
        apply_styles(self.sep_custom, sep_style)
        apply_styles(self.sep_launcher, sep_style)
