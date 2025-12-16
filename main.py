#!/home/sigma/projects/repos/locus/.venv/bin/python3
# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: basic
# ruff: ignore

import sys
import os
import time
import setproctitle

import subprocess
import json
from typing_extensions import final

import style
from datetime import datetime as dt
from config import APPNAME
import gi
import threading


# For GTK4 Layer Shell to get linked before libwayland-client we must explicitly load it before importing with gi
from ctypes import CDLL

CDLL("libgtk4-layer-shell.so")

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")

from gi.repository import GLib, Gdk, Gtk, Gtk4LayerShell as GtkLayerShell  # noqa: E402

import i3ipc  # noqa: E402

setproctitle.setproctitle(APPNAME)


def kill_previous_process():
    """Kill previous locus processes if running"""
    try:
        # Get current process ID to avoid killing ourselves
        current_pid = os.getpid()

        # Find all locus processes except current one
        result = subprocess.run(
            ["pgrep", "-f", APPNAME], capture_output=True, text=True
        )

        if result.returncode == 0:
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                if pid and int(pid) != current_pid:
                    try:
                        os.kill(int(pid), 9)  # SIGKILL to ensure immediate termination
                        print(f"Killed previous locus process {pid}")
                    except ProcessLookupError:
                        pass  # Process already terminated
                    except PermissionError:
                        pass  # No permission to kill

            # Wait a bit for processes to fully terminate
            time.sleep(0.5)
    except Exception:
        pass  # Ignore errors, continue execution


# Kill previous processes before starting
kill_previous_process()


TIME_PATH = os.path.expanduser("~/.time")


def apply_styles(widget: Gtk.Box | Gtk.Widget | Gtk.Label, css: str):
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode())
    context = widget.get_style_context()
    context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def read_time() -> str:
    try:
        return open(TIME_PATH).read().strip()
    except FileNotFoundError:
        return "0"  # Default to 0 if file doesn't exist


async def is_running(process_name: str) -> bool:
    try:
        if not os.name == "nt":
            output = subprocess.check_output(["pgrep", process_name])
            return output.lower() != b""
    except subprocess.CalledProcessError:
        return False
    return False


def get_default_styling() -> str:
    return str(
        "  margin: %spx; margin-top: %spx; padding: %spx; border: %spx solid; border-radius: %spx; "
        % (
            style.WIDGET_MARGINS[0],
            style.WIDGET_MARGINS[0],
            style.PADDING,
            style.BORDER,
            style.BORDER_ROUNDING,
        ),
    )


def VBox(spacing: int = 6, hexpand: bool = False, vexpand: bool = False) -> Gtk.Box:
    return Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=spacing,
        hexpand=hexpand,
        vexpand=vexpand,
    )


def HBox(spacing: int = 6, hexpand: bool = False, vexpand: bool = False) -> Gtk.Box:
    return Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        spacing=spacing,
        hexpand=hexpand,
        vexpand=vexpand,
    )


# Cache for battery path to avoid repeated filesystem checks
_battery_path_cache = None


def get_battery_path() -> str | None:
    """Get the battery path, caching the result"""
    global _battery_path_cache
    if _battery_path_cache is not None:
        return _battery_path_cache

    # Try to get battery info from /sys/class/power_supply/
    battery_path = "/sys/class/power_supply/BAT0"  # Most common battery path
    if os.path.exists(battery_path):
        _battery_path_cache = battery_path
        return battery_path

    # Try alternative battery paths
    for i in range(10):
        alt_path = f"/sys/class/power_supply/BAT{i}"
        if os.path.exists(alt_path):
            _battery_path_cache = alt_path
            return alt_path

    _battery_path_cache = None
    return None


def get_battery_status() -> str:
    """Get battery percentage and charging status"""
    try:
        battery_path = get_battery_path()
        if battery_path is None:
            return "No Battery"

        # Read capacity and status in one go using subprocess for efficiency
        result = subprocess.run(
            ["cat", f"{battery_path}/capacity", f"{battery_path}/status"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                capacity = lines[0].strip()
                status = lines[1].strip()
                return f"{capacity} {status}"

        # Fallback to individual file reads if cat fails
        with open(f"{battery_path}/capacity", "r") as f:
            capacity = int(f.read().strip())
        with open(f"{battery_path}/status", "r") as f:
            status = f.read().strip()
        return f"{capacity} {status}"

    except (
        FileNotFoundError,
        ValueError,
        IOError,
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
    ):
        # Fallback to upower if available
        try:
            result = subprocess.run(
                ["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.split("\n")
                percentage = None
                state = None

                for line in lines:
                    if "percentage" in line.lower():
                        percentage = line.split(":")[-1].strip()
                    elif "state" in line.lower():
                        state = line.split(":")[-1].strip()

                if percentage and state:
                    return f"{percentage} {state}"
                elif percentage:
                    return percentage

            return "Battery Unknown"
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            return "No Battery"


@final
class Workspace:
    def __init__(self, name: str, focused: bool):
        self.name = name
        self.focused = focused
        self.num = int(name) if name.isdigit() else 999


class WMClient:
    def get_workspaces(self) -> list[Workspace]:
        raise NotImplementedError()

    def start_event_listener(self, callback) -> None:
        raise NotImplementedError()


class SwayClient(WMClient):
    def __init__(self):
        self.i3 = i3ipc.Connection()

    def get_workspaces(self) -> list[Workspace]:
        try:
            workspaces = self.i3.get_workspaces()
            return [Workspace(ws.name, ws.focused) for ws in workspaces]
        except Exception:
            return []

    def start_event_listener(self, callback) -> None:
        def on_workspace(i3, e):
            GLib.idle_add(callback)

        self.i3.on("workspace", on_workspace)
        thread = threading.Thread(target=self.i3.main)
        thread.daemon = True
        thread.start()


class HyprlandClient(WMClient):
    def __init__(self):
        self.signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")

    def get_workspaces(self) -> list[Workspace]:
        try:
            result = subprocess.run(
                ["hyprctl", "workspaces", "-j"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode != 0:
                return []

            # Get active workspace to mark focused
            active_res = subprocess.run(
                ["hyprctl", "activeworkspace", "-j"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            active_id = -1
            if active_res.returncode == 0:
                try:
                    active_data = json.loads(active_res.stdout)
                    active_id = active_data.get("id", -1)
                except:
                    pass

            workspaces_data = json.loads(result.stdout)
            workspaces = []
            for ws in workspaces_data:
                # Hyprland workspaces have an ID and a name. Usually we use ID.
                # If name is different, we might prefer that.
                name = str(ws.get("id", "?"))
                is_focused = ws.get("id") == active_id
                workspaces.append(Workspace(name, is_focused))

            return workspaces
        except Exception as e:
            print(f"Hyprland error: {e}")
            return []

    def start_event_listener(self, callback) -> None:
        if not self.signature:
            return

        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
        socket_path = f"{runtime_dir}/hypr/{self.signature}/.socket2.sock"

        def listen():
            import socket

            while True:
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.connect(socket_path)

                    buffer = ""
                    while True:
                        data = s.recv(1024)
                        if not data:
                            break
                        buffer += data.decode("utf-8")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            # workspace events: workspace>>NAME, destroyworkspace>>NAME, createworkspace>>NAME, focusworkspace>>NAME
                            if "workspace" in line:
                                GLib.idle_add(callback)
                except Exception as e:
                    print(f"Hyprland socket error: {e}")
                    time.sleep(1)
                finally:
                    s.close()
                    time.sleep(1)

        thread = threading.Thread(target=listen)
        thread.daemon = True
        thread.start()


def detect_wm() -> WMClient:
    # Check for Hyprland
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return HyprlandClient()

    # Default to Sway/i3
    return SwayClient()


@final
class Popup(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(
            **kwargs,
            title="popup",
            show_menubar=False,
            child=None,
            default_width=300,
            default_height=50,
            destroy_with_parent=True,
            hide_on_close=True,
            resizable=False,
            visible=False,
        )

        self.entry = Gtk.Entry()
        self.entry.connect("activate", self.on_entry_activate)
        self.set_child(self.entry)

        # Layer shell setup
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, 70)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, 0)

        apply_styles(
            self.entry,
            """
            entry {
                background: #0e1418;
                color: #ebdbb2;
                border: 1px solid #ebdbb2;
                border-radius: 5px;
                padding: 5px;
                font-size: 16px;
                font-family: Iosevka;
            }
        """,
        )

    def on_entry_activate(self, entry):
        command = entry.get_text().strip()
        if command:
            try:
                subprocess.Popen(command, shell=True)
            except Exception as e:
                print(f"Failed to run command: {e}")
        self.hide()

    def show_popup(self):
        self.show()
        self.entry.grab_focus()


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

        self.main_box = HBox(spacing=0, hexpand=True)
        self.set_child(self.main_box)

        self.left_box = HBox(spacing=0)
        self.fixed = Gtk.Fixed()
        self.workspaces_label = Gtk.Label()
        self.fixed.put(self.workspaces_label, 0, 0)
        self.sep_left = Gtk.Label.new(" | ")
        self.binding_state_label = Gtk.Label()
        self.sep_emacs = Gtk.Label.new(" | ")
        self.emacs_clock_label = Gtk.Label()

        # Create right section: time | battery
        self.right_box = HBox(spacing=0)
        self.time_label = Gtk.Label()
        self.sep_right = Gtk.Label.new(" | ")
        self.battery_label = Gtk.Label()

        self.previous_focused = None
        self.update_time()
        self.update_battery()
        self.update_workspaces()
        self.update_binding_state()
        self.update_emacs_clock()

        # Add to left box
        self.left_box.append(self.fixed)
        self.left_box.append(self.sep_left)
        self.left_box.append(self.binding_state_label)
        self.left_box.append(self.sep_emacs)
        self.left_box.append(self.emacs_clock_label)

        # Add to right box
        self.right_box.append(self.time_label)
        self.right_box.append(self.sep_right)
        self.right_box.append(self.battery_label)

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
                color: #ebdbb2;
                font-size: 32px;
                font-weight: normal;
                font-family: monospace;
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
        apply_styles(self.sep_left, sep_style)
        apply_styles(self.sep_right, sep_style)
        apply_styles(self.sep_emacs, sep_style)


def on_activate(app: Gtk.Application):
    display = Gdk.Display.get_default()
    if not display:
        return

    monitors = display.get_monitors()
    n_monitors = monitors.get_n_items()

    # Define height once to ensure window size and reserved space match
    BAR_HEIGHT = 20

    for i in range(n_monitors):
        monitor = monitors.get_item(i)

        geometry = monitor.get_geometry()

        status_win = StatusBar(application=app)
        GtkLayerShell.init_for_window(status_win)
        GtkLayerShell.set_monitor(status_win, monitor)

        GtkLayerShell.set_layer(status_win, GtkLayerShell.Layer.BOTTOM)

        GtkLayerShell.set_anchor(status_win, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_anchor(status_win, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_anchor(status_win, GtkLayerShell.Edge.BOTTOM, True)

        GtkLayerShell.set_margin(status_win, GtkLayerShell.Edge.LEFT, 0)
        GtkLayerShell.set_margin(status_win, GtkLayerShell.Edge.RIGHT, 0)
        GtkLayerShell.set_margin(status_win, GtkLayerShell.Edge.BOTTOM, 0)

        status_win.set_size_request(geometry.width, BAR_HEIGHT)

        GtkLayerShell.auto_exclusive_zone_enable(status_win)

        status_win.present()


app = Gtk.Application(application_id="com.example")
app.connect("activate", on_activate)

display = Gdk.Display.get_default()
if not display:
    sys.exit()

# get all the monitors, then create a window on each monitor
monitors = display.get_monitors()

app.run(None)

app.connect("shutdown", lambda *_: sys.exit(0))
