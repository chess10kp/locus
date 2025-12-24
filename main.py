#!/home/sigma/projects/repos/locus/.venv/bin/python3
# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import sys
import os
import time
import setproctitle  # pyright: ignore
import subprocess

# Add current directory to path for absolute imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.config import APPNAME
import gi

# Removed CDLL preload - LD_PRELOAD in run.sh should be sufficient

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")

from gi.repository import Gdk, Gtk, Gtk4LayerShell as GtkLayerShell, GLib  # noqa: E402  # pyright: ignore

# Initialize GTK immediately after imports, before any other modules
Gtk.init()

from core.status_bar import StatusBar  # noqa: E402
from core import status_bars  # noqa: E402
from utils.deps import check_volume_utilities, check_brightness_utilities  # noqa: E402


def kill_previous_process():
    """Kill previous locus processes if running"""
    try:
        current_pid = os.getpid()

        result = subprocess.run(
            ["pgrep", "-f", APPNAME], capture_output=True, text=True
        )

        if result.returncode == 0:
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                if pid and int(pid) != current_pid:
                    try:
                        os.kill(int(pid), 9)  # SIGKILL
                    except ProcessLookupError:
                        pass
                    except PermissionError:
                        pass

            time.sleep(0.5)
    except Exception:
        pass


monitor_to_window = {}  # Global dict to map monitors to their status bars


def on_activate(app: Gtk.Application):
    global status_bars
    display = Gdk.Display.get_default()
    if not display:
        return

    monitors = display.get_monitors()
    n_monitors = monitors.get_n_items()

    BAR_HEIGHT = 20

    for i in range(n_monitors):
        monitor = monitors.get_item(i)

        geometry = monitor.get_geometry()

        status_win = StatusBar(application=app)
        GtkLayerShell.init_for_window(status_win)
        GtkLayerShell.set_monitor(status_win, monitor)

        GtkLayerShell.set_layer(status_win, GtkLayerShell.Layer.TOP)

        GtkLayerShell.set_anchor(status_win, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_anchor(status_win, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_anchor(status_win, GtkLayerShell.Edge.TOP, True)

        GtkLayerShell.set_margin(status_win, GtkLayerShell.Edge.LEFT, 0)
        GtkLayerShell.set_margin(status_win, GtkLayerShell.Edge.RIGHT, 0)
        GtkLayerShell.set_margin(status_win, GtkLayerShell.Edge.TOP, 0)

        status_win.set_size_request(geometry.width, BAR_HEIGHT)

        GtkLayerShell.auto_exclusive_zone_enable(status_win)

        status_win.present()
        status_bars.append(status_win)
        monitor_to_window[monitor] = status_win

    # Define signal callback for monitors list changes
    def on_monitors_changed(model, position, removed, added):
        # Get current monitors
        current_monitors = [model.get_item(i) for i in range(model.get_n_items())]

        # Destroy all existing bars
        for monitor, status_win in list(monitor_to_window.items()):
            status_win.cleanup()
            status_win.destroy()
            status_bars.remove(status_win)
        monitor_to_window.clear()

        # Schedule recreation after a short delay to allow geometry update
        def recreate_bars(monitors):
            for monitor in monitors:
                geometry = monitor.get_geometry()
                status_win = StatusBar(application=app)
                GtkLayerShell.init_for_window(status_win)
                GtkLayerShell.set_monitor(status_win, monitor)
                GtkLayerShell.set_layer(status_win, GtkLayerShell.Layer.TOP)
                GtkLayerShell.set_anchor(status_win, GtkLayerShell.Edge.LEFT, True)
                GtkLayerShell.set_anchor(status_win, GtkLayerShell.Edge.RIGHT, True)
                GtkLayerShell.set_anchor(status_win, GtkLayerShell.Edge.TOP, True)
                GtkLayerShell.set_margin(status_win, GtkLayerShell.Edge.LEFT, 0)
                GtkLayerShell.set_margin(status_win, GtkLayerShell.Edge.RIGHT, 0)
                GtkLayerShell.set_margin(status_win, GtkLayerShell.Edge.TOP, 0)
                status_win.set_size_request(geometry.width, BAR_HEIGHT)
                GtkLayerShell.auto_exclusive_zone_enable(status_win)
                status_win.present()
                status_win.queue_resize()
                status_bars.append(status_win)
                monitor_to_window[monitor] = status_win
            return False  # Remove the timeout

        GLib.timeout_add(100, recreate_bars, current_monitors)  # 100ms delay

    # Connect to monitors list changes
    monitors.connect("items-changed", on_monitors_changed)

    # Start IPC server on the first statusbar
    if status_bars:
        status_bars[0].start_ipc_server()


def on_shutdown(app: Gtk.Application):
    """Clean up all StatusBar instances and their threads."""
    global status_bars
    for status_bar in status_bars:
        try:
            status_bar.cleanup()
        except Exception as e:
            pass
    status_bars.clear()


def main():
    """Main entry point for the locus application."""
    setproctitle.setproctitle(APPNAME)

    kill_previous_process()

    # Check for required utilities
    vol_error = check_volume_utilities()
    if vol_error:
        print(f"Warning: {vol_error}", file=sys.stderr)

    bright_error = check_brightness_utilities()
    if bright_error:
        print(f"Warning: {bright_error}", file=sys.stderr)

    app = Gtk.Application(application_id="com.example")
    app.connect("activate", on_activate)
    app.connect("shutdown", on_shutdown)

    display = Gdk.Display.get_default()
    if not display:
        sys.exit()

    monitors = display.get_monitors()

    app.run(None)


if __name__ == "__main__":
    main()
