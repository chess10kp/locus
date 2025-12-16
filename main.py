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
import argparse

from config import APPNAME
import gi

# For GTK4 Layer Shell to get linked before libwayland-client we must explicitly load it before importing with gi
from ctypes import CDLL

CDLL("libgtk4-layer-shell.so")

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")

from gi.repository import Gdk, Gtk, Gtk4LayerShell as GtkLayerShell  # noqa: E402

from utils import load_desktop_apps  # noqa: E402
from status_bar import StatusBar  # noqa: E402

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

parser = argparse.ArgumentParser()
parser.add_argument(
    "--launcher",
    action="store_true",
    help="Run launcher in CLI mode, reading from stdin",
)
args = parser.parse_args()

if args.launcher:
    apps = load_desktop_apps()
    input_text = sys.stdin.read().strip()
    for app in apps:
        if input_text.lower() in app["name"].lower():
            try:
                subprocess.Popen([app["exec"]], shell=False)
                sys.exit(0)
            except Exception as e:
                print(f"Failed to launch {app['name']}: {e}")
                sys.exit(1)
    print("App not found")
    sys.exit(1)


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
