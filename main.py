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
from exceptions import (
    EmacsUnavailableException,
    NotLinuxException,
    NoValueFoundException,
)

import style
from datetime import datetime as dt
from config import CITY, APPNAME
import asyncio
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
                        os.kill(int(pid), 15)  # SIGTERM
                        print(f"Killed previous locus process {pid}")
                    except ProcessLookupError:
                        pass  # Process already terminated
                    except PermissionError:
                        pass  # No permission to kill
    except Exception:
        pass  # Ignore errors, continue execution


# Kill previous processes before starting
kill_previous_process()


TIME_PATH = os.path.expanduser("~/.time")
TASKS_VIS_PATH = os.path.expanduser("~/.dashboard_tasks_visible")


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


def read_tasks_visible() -> bool:
    try:
        return open(TASKS_VIS_PATH).read().strip() == "1"
    except FileNotFoundError:
        return True


def write_tasks_visible(visible: bool) -> None:
    try:
        with open(TASKS_VIS_PATH, "w") as f:
            f.write("1" if visible else "0")
    except Exception:
        # best-effort persistence; ignore errors
        pass


async def is_running(process_name: str) -> bool:
    try:
        if not os.name == "nt":
            output = subprocess.check_output(["pgrep", process_name])
            return output.lower() != b""
    except subprocess.CalledProcessError:
        return False


async def get_agenda() -> str:
    """Gets the agenda for today, then closes the agenda buffer"""

    emacs_agenda = "(progn \
    (require 'org-agenda) \
    (let ((org-agenda-span 'day)) \
    (org-batch-agenda \"a\")))"

    output = subprocess.run(
        ["emacs", "-batch", "-l", "~/.emacs.d/init.el", "-eval", emacs_agenda],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout

    return output


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


async def parse_agenda() -> list[str]:
    try:
        agenda = await get_agenda()
    except EmacsUnavailableException as e:
        print(f"Error: {e}")
        sys.exit(-1)

    agenda = agenda.splitlines()
    todos = list(
        map(
            lambda x: x[x.find(":") + 1 :].strip(),
            filter(lambda x: "todo" in x and "closed" not in x.lower(), agenda),
        )
    )
    return todos


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


def get_battery_status() -> str:
    """Get battery percentage and charging status"""
    try:
        # Try to get battery info from /sys/class/power_supply/
        battery_path = "/sys/class/power_supply/BAT0"  # Most common battery path
        if not os.path.exists(battery_path):
            # Try alternative battery paths
            for i in range(10):
                alt_path = f"/sys/class/power_supply/BAT{i}"
                if os.path.exists(alt_path):
                    battery_path = alt_path
                    break
            else:
                return "No Battery"

        # Read capacity
        with open(f"{battery_path}/capacity", "r") as f:
            capacity = int(f.read().strip())

        # Read status
        with open(f"{battery_path}/status", "r") as f:
            status = f.read().strip()

        return f"{capacity}"

    except (FileNotFoundError, ValueError, IOError):
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

                if percentage:
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

        self.left_box = HBox(spacing=5)
        self.workspaces_label = Gtk.Label()
        self.sep_left = Gtk.Label.new(" | ")
        self.binding_state_label = Gtk.Label()

        # Create right section: time | battery
        self.right_box = HBox(spacing=5)
        self.time_label = Gtk.Label()
        self.sep_right = Gtk.Label.new(" | ")
        self.battery_label = Gtk.Label()

        self.update_time()
        self.update_battery()
        self.update_workspaces()
        self.update_binding_state()

        # Add to left box
        self.left_box.append(self.workspaces_label)
        self.left_box.append(self.sep_left)
        self.left_box.append(self.binding_state_label)

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

    def update_time(self):
        """Update time display"""
        current_time = dt.now().strftime("%H:%M:%S")
        self.time_label.set_text(current_time)

    def update_battery(self):
        """Update battery display"""
        battery_status = get_battery_status()
        self.battery_label.set_text(battery_status)

    def update_workspaces(self):
        """Update workspaces display"""
        try:
            workspaces = self.wm_client.get_workspaces()
            ws_sorted = sorted(
                workspaces,
                key=lambda ws: (
                    ws.num,
                    ws.name,
                ),
            )
            text_parts = []
            for ws in ws_sorted:
                name = ws.name
                if ws.focused:
                    name = (
                        f'<span background="#ebdbb2" foreground="#0e1419">{name}</span>'
                    )
                text_parts.append(name)
            self.workspaces_label.set_markup(" ".join(text_parts))
        except Exception:
            self.workspaces_label.set_text("?")

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

    def apply_status_bar_styles(self):
        """Apply CSS styling to the status bar like Emacs modeline"""
        apply_styles(
            self,
            """
            window {
                background: #0e1418;
            }
            """,
        )

        apply_styles(
            self.main_box,
            """
            box {
                background: transparent;
                padding: 0;
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
        apply_styles(self.sep_left, sep_style)
        apply_styles(self.sep_right, sep_style)


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

        # if i == 0:
        # dashboard_win = Dashboard(application=app)
        # GtkLayerShell.init_for_window(dashboard_win)
        # GtkLayerShell.set_monitor(dashboard_win, monitor)
        # GtkLayerShell.set_layer(dashboard_win, GtkLayerShell.Layer.BOTTOM)
        # GtkLayerShell.set_anchor(dashboard_win, GtkLayerShell.Edge.TOP, True)
        # GtkLayerShell.set_anchor(dashboard_win, GtkLayerShell.Edge.RIGHT, True)
        # dashboard_win.present()


app = Gtk.Application(application_id="com.example")
app.connect("activate", on_activate)

display = Gdk.Display.get_default()
if not display:
    sys.exit()

# get all the monitors, then create a window on each monitor
monitors = display.get_monitors()

app.run(None)

app.connect("shutdown", lambda *_: sys.exit(0))
