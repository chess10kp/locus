#!/usr/bin/env python3
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
        else:
            raise NotLinuxException()
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


def get_sway_workspaces() -> str:
    """Get open Sway workspaces"""
    try:
        # Use swaymsg to get workspaces
        result = subprocess.run(
            ["swaymsg", "-t", "get_workspaces"],
            capture_output=True,
            text=True,
            timeout=2,
        )

        if result.returncode == 0:
            workspaces = json.loads(result.stdout)
            # Get workspace numbers, sorted
            ws_nums = sorted([str(ws["num"]) for ws in workspaces])
            return f"󰍹 {' '.join(ws_nums)}"
        else:
            return "󰍹 ?"

    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        FileNotFoundError,
    ):
        return "󰍹 ?"


def get_sway_submap() -> str:
    """Get current Sway submap/mode"""
    try:
        # Use swaymsg to get binding state
        result = subprocess.run(
            ["swaymsg", "-t", "get_binding_state"],
            capture_output=True,
            text=True,
            timeout=2,
        )

        if result.returncode == 0:
            state = json.loads(result.stdout)
            mode = state.get("name", "default")
            return f"Mode: {mode}"
        else:
            return "Mode: default"

    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        FileNotFoundError,
    ):
        return "Mode: default"


def timeBox() -> Gtk.Box:
    timeBox = Gtk.Box()
    timeButton = Gtk.Button(label=read_time())

    def on_time_button_clicked(_w: Gtk.Button) -> None:
        new_label = timeButton.get_label()
        if new_label is not None:
            with open(TIME_PATH, "w") as f:
                f.write(new_label)
        else:
            raise NoValueFoundException("timeButton does not hold a label value")

        timeButton.set_label(str(int(new_label) + 1))

    timeButton.connect("clicked", on_time_button_clicked)

    timeBox.append(timeButton)

    return timeBox


def Time() -> Gtk.Box:
    """Returns time widget with time, and day"""
    timeBox = VBox(8)  # More compact spacing

    time_widget = Gtk.Label(label=dt.now().strftime("%I:%M %p"))

    passingOfTimeBox = HBox(20)

    def read_day_date():
        return dt.now().strftime("%A, %B %d")

    dayDataButton = Gtk.Label(label=f"{read_day_date()}")

    def days_passed_this_year():
        today = dt.now()
        year_start = dt(today.year, 1, 1)
        return (today - year_start).days + 1

    numDaysInThisYearPassedButton = Gtk.Label(label=f"{days_passed_this_year()} days")
    numHoursPassedThisYearButton = Gtk.Label(
        label=f"{days_passed_this_year() * 24} hours"
    )
    numMinutesPassedThisYearButton = Gtk.Label(
        label=f"{days_passed_this_year() * 24 * 60} minutes"
    )

    def update_time():
        return dt.now().strftime("%I:%M %p")

    GLib.timeout_add_seconds(60, (lambda: time_widget.set_label(update_time()) or True))
    GLib.timeout_add_seconds(
        600, (lambda: dayDataButton.set_label(read_day_date()) or True)
    )

    GLib.timeout_add_seconds(
        7200,
        (
            lambda: numDaysInThisYearPassedButton.set_label(
                f"{days_passed_this_year()} days"
            )
            or True
        ),
    )
    GLib.timeout_add_seconds(
        600,
        (
            lambda: numHoursPassedThisYearButton.set_label(
                f"{days_passed_this_year() * 24} hours"
            )
            or True
        ),
    )
    GLib.timeout_add_seconds(
        300,
        (
            lambda: numMinutesPassedThisYearButton.set_label(
                f"{days_passed_this_year() * 24 * 60} minutes"
            )
            or True
        ),
    )

    apply_styles(
        time_widget,
        "label {font-size: 100px; font-weight: bold; color: #ffffff; text-shadow: 3px 3px 6px rgba(0,0,0,0.8), 0px 0px 20px rgba(0,0,0,0.5);}",
    )
    apply_styles(
        dayDataButton,
        "label {font-size: 26px; color: #ffb000; font-weight: 500; margin-bottom: 12px; font-family: monospace; text-shadow: 0 0 8px rgba(255,176,0,0.3);}",
    )

    apply_styles(
        numDaysInThisYearPassedButton,
        "label {font-size: 16px; color: #ffffff; font-weight: 400; margin: 4px 12px; font-family: monospace;}",
    )
    apply_styles(
        numHoursPassedThisYearButton,
        "label {font-size: 16px; color: #ffffff; font-weight: 400; margin: 4px 12px; font-family: monospace;}",
    )
    apply_styles(
        numMinutesPassedThisYearButton,
        "label {font-size: 16px; color: #ffffff; font-weight: 400; margin: 4px 12px; font-family: monospace;}",
    )

    # Add calendar icon to date
    dayDataButton.set_label(f"{read_day_date()}")

    passingOfTimeBox.append(numDaysInThisYearPassedButton)
    passingOfTimeBox.append(numHoursPassedThisYearButton)
    passingOfTimeBox.append(numMinutesPassedThisYearButton)

    timeBox.append(dayDataButton)
    timeBox.append(passingOfTimeBox)

    return timeBox


def Agenda(parent_window: Gtk.ApplicationWindow | None = None) -> Gtk.Box:
    """Returns Agenda Widget"""
    agenda_box = VBox(8)  # More compact spacing

    # Create scrollable container for the task list
    scrolled_window = Gtk.ScrolledWindow()
    # Allow horizontal scrolling and automatic vertical scrollbars
    scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrolled_window.set_min_content_height(600)  # Minimum height to force stretching
    # set a reasonable min width so horizontal scrolling is used instead of wrapping
    scrolled_window.set_min_content_width(360)
    scrolled_window.set_propagate_natural_height(True)

    agenda_ibox = VBox(2)  # Very compact spacing for terminal look
    scrolled_window.set_child(agenda_ibox)

    def update():
        agenda = asyncio.run(parse_agenda())

        # clear existing items
        child = agenda_ibox.get_first_child()
        while child:
            prev = child
            child = child.get_next_sibling()
            agenda_ibox.remove(prev)

        for item in agenda:
            # Ensure labels don't wrap so long items produce horizontal scrolling
            label = Gtk.Label(label=f"{item}")
            try:
                label.set_wrap(False)
            except Exception:
                # older GTK versions may not have set_wrap; ignore
                pass
            label.set_halign(Gtk.Align.START)

            apply_styles(
                label,
                "label { color: #e0e0e0; font-size: 16px; font-weight: 400; margin: 3px 0; padding: 2px 0; font-family: monospace; }",
            )
            GLib.idle_add(agenda_ibox.append, label)

    update()

    # Add a header with a toggle to show/hide the task list. Persist state across runs.
    header = HBox()
    toggle = Gtk.ToggleButton()

    # initialize from persisted value
    initial_visible = read_tasks_visible()
    toggle.set_active(initial_visible)
    toggle.set_label("Hide Tasks" if initial_visible else "Show Tasks")

    # make the toggle less conspicuous (small, flat)
    apply_styles(
        toggle,
        "button { background-color: transparent; color: #bdbdbd; padding: 4px 8px; border-radius: 4px; font-size: 12px; border: none; } button:checked { color: #ffffff; }",
    )

    # Use a Revealer to animate the task list sliding in/out vertically while preserving width
    revealer = Gtk.Revealer()
    try:
        revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
    except Exception:
        # older GTK may have different enums; ignore and use default
        pass
    revealer.set_transition_duration(300)
    # ensure a reserved width so hiding doesn't collapse horizontal space
    try:
        revealer.set_min_content_width(360)
    except Exception:
        pass

    # put the scrolled window inside the revealer
    revealer.set_child(scrolled_window)
    revealer.set_reveal_child(initial_visible)

    def on_toggle(button: Gtk.ToggleButton) -> None:
        active = button.get_active()
        button.set_label("Hide Tasks" if active else "Show Tasks")
        write_tasks_visible(active)
        # animate reveal/hide
        revealer.set_reveal_child(active)

    toggle.connect("toggled", on_toggle)
    header.append(toggle)

    # Append header and the revealer that contains the scrollable task list
    agenda_box.append(header)
    agenda_box.append(revealer)

    GLib.timeout_add_seconds(30, (lambda: update() or True))

    return agenda_box


@final
class Dashboard(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(
            **kwargs,
            title="dashboard",
            show_menubar=False,
            child=None,
            fullscreened=False,
            destroy_with_parent=True,
            hide_on_close=False,
            resizable=False,
            visible=True,
        )

        self.main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12, homogeneous=False
        )

        # Set fixed width to prevent resizing
        self.set_size_request(400, 100)

        self.set_child(self.main_box)

        # Make the window background transparent with terminal-like shadow
        apply_styles(
            self,
            "window { background: transparent; box-shadow: 0 0 0 1px #333, 0 6px 24px rgba(0,0,0,0.8), inset 0 1px 0 rgba(255,255,255,0.05); }",
        )

        # Single unified section containing both time and agenda
        self.unified_section = VBox(12)
        self.unified_section.append(Time())
        self.unified_section.append(Agenda(self))
        self.main_box.append(self.unified_section)

        apply_styles(self.main_box, "box { background: transparent; padding: 8px; }")
        apply_styles(
            self.unified_section,
            "box {background: rgba(0,0,0,0.85); padding: 14px; border-radius: 6px; margin: 2px; box-shadow: 0 3px 12px rgba(0,0,0,0.6); backdrop-filter: blur(6px); border: 1px solid #444;}",
        )


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

        self.main_box = HBox(spacing=0, hexpand=True)
        self.set_child(self.main_box)

        self.left_box = HBox(spacing=5)
        self.workspaces_label = Gtk.Label()
        self.sep_left = Gtk.Label.new(" | ")
        # self.submap_label = Gtk.Label()

        # Create right section: time | battery
        self.right_box = HBox(spacing=5)
        self.time_label = Gtk.Label()
        self.sep_right = Gtk.Label.new(" | ")
        self.battery_label = Gtk.Label()

        self.update_time()
        self.update_battery()
        self.update_workspaces()
        # self.update_submap()

        # Add to left box
        self.left_box.append(self.workspaces_label)
        self.left_box.append(self.sep_left)
        # self.left_box.append(self.submap_label)

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
        self.i3 = i3ipc.Connection()
        self.i3.on("workspace", self.on_workspace)
        # self.i3.on("mode", self.on_mode)

        self.i3_thread = threading.Thread(target=self.i3.main)
        self.i3_thread.daemon = True
        self.i3_thread.start()

        GLib.timeout_add_seconds(60, self.update_time_callback)
        GLib.timeout_add_seconds(60, self.update_battery_callback)
        # GLib.timeout_add_seconds(1, self.update_submap_callback)

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
            workspaces = self.i3.get_workspaces()
            ws_sorted = sorted(
                workspaces,
                key=lambda ws: (
                    not ws.name.isdigit(),
                    int(ws.name) if ws.name.isdigit() else 0,
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

    # def update_submap(self):
    #     """Update submap display"""
    #     try:
    #         state = self.i3.get_binding_state()
    #         mode = state.name
    #         self.submap_label.set_text(mode)
    #     except Exception:
    #         self.submap_label.set_text("default")

    def on_workspace(self, i3, e):
        """Handle workspace event"""
        GLib.idle_add(self.update_workspaces)

    # def on_mode(self, i3, e):
    #     """Handle mode event"""
    #     GLib.idle_add(self.update_submap)

    def update_time_callback(self) -> bool:
        """Callback for time updates"""
        self.update_time()
        return True

    def update_battery_callback(self) -> bool:
        """Callback for battery updates"""
        self.update_battery()
        return True

    # def update_submap_callback(self) -> bool:
    #     """Callback for submap updates"""
    #     self.update_submap()
    #     return True

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
        # apply_styles(self.submap_label, label_style)
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

        if i == 0:
            dashboard_win = Dashboard(application=app)
            GtkLayerShell.init_for_window(dashboard_win)
            GtkLayerShell.set_monitor(dashboard_win, monitor)
            GtkLayerShell.set_layer(dashboard_win, GtkLayerShell.Layer.BOTTOM)
            GtkLayerShell.set_anchor(dashboard_win, GtkLayerShell.Edge.TOP, True)
            GtkLayerShell.set_anchor(dashboard_win, GtkLayerShell.Edge.RIGHT, True)
            dashboard_win.present()


app = Gtk.Application(application_id="com.example")
app.connect("activate", on_activate)

display = Gdk.Display.get_default()
if not display:
    sys.exit()

# get all the monitors, then create a window on each monitor
monitors = display.get_monitors()

app.run(None)

app.connect("shutdown", lambda *_: sys.exit(0))
