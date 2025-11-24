#!/usr/bin/env python3
# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# basic
# ruff: ignore

import sys
import os
import subprocess
import json
from datetime import datetime as dt
from typing_extensions import final

import gi

# For GTK4 Layer Shell to get linked before libwayland-client we must explicitly load it before importing with gi
from ctypes import CDLL

CDLL("libgtk4-layer-shell.so")

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")

from gi.repository import GLib, Gdk, Gtk, Gtk4LayerShell as GtkLayerShell  # noqa: E402


def apply_styles(widget: Gtk.Box | Gtk.Widget | Gtk.Label, css: str):
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode())
    context = widget.get_style_context()
    context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


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
        
        status_icon = "⚡" if status == "Charging" else "🔋"
        return f"{status_icon} {capacity}%"
    
    except (FileNotFoundError, ValueError, IOError):
        # Fallback to upower if available
        try:
            result = subprocess.run(
                ["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                percentage = None
                state = None
                
                for line in lines:
                    if 'percentage' in line.lower():
                        percentage = line.split(':')[-1].strip()
                    elif 'state' in line.lower():
                        state = line.split(':')[-1].strip()
                
                if percentage:
                    status_icon = "⚡" if state and "charging" in state.lower() else "🔋"
                    return f"{status_icon} {percentage}"
            
            return "Battery Unknown"
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return "No Battery"


def get_hyprland_workspace() -> str:
    """Get current Hyprland workspace"""
    try:
        # Use hyprctl to get active workspace
        result = subprocess.run(
            ["hyprctl", "activeworkspace", "-j"],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if result.returncode == 0:
            workspace_info = json.loads(result.stdout)
            workspace_id = workspace_info.get("id", "?")
            workspace_name = workspace_info.get("name", str(workspace_id))
            return f"󰍹 {workspace_name}"
        else:
            return "󰍹 ?"
    
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        # Fallback: try to get from socket directly
        try:
            # Get Hyprland instance signature
            hypr_instance = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
            if hypr_instance:
                # This is more complex to implement with socket communication
                # For now, return a simple fallback
                return "󰍹 ?"
            return "󰍹 ?"
        except Exception:
            return "󰍹 ?"


def HBox(spacing: int = 6, hexpand: bool = False, vexpand: bool = False) -> Gtk.Box:
    return Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        spacing=spacing,
        hexpand=hexpand,
        vexpand=vexpand,
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

        # Create main horizontal box for status bar items
        self.main_box = HBox(spacing=20, hexpand=True)
        self.set_child(self.main_box)

        # Set fixed size for status bar
        self.set_size_request(300, 40)

        # Create status items
        self.time_label = Gtk.Label()
        self.battery_label = Gtk.Label()
        self.workspace_label = Gtk.Label()

        # Initialize labels
        self.update_time()
        self.update_battery()
        self.update_workspace()

        # Add labels to main box
        self.main_box.append(self.time_label)
        self.main_box.append(self.battery_label)
        self.main_box.append(self.workspace_label)

        # Apply styling
        self.apply_status_bar_styles()

        # Set up timers for updates
        # Update time every second
        GLib.timeout_add_seconds(1, self.update_time_callback)
        # Update battery every 30 seconds
        GLib.timeout_add_seconds(30, self.update_battery_callback)
        # Update workspace every 2 seconds (for responsiveness)
        GLib.timeout_add_seconds(2, self.update_workspace_callback)

    def update_time(self):
        """Update time display"""
        current_time = dt.now().strftime("%H:%M:%S")
        self.time_label.set_text(f"🕐 {current_time}")

    def update_battery(self):
        """Update battery display"""
        battery_status = get_battery_status()
        self.battery_label.set_text(battery_status)

    def update_workspace(self):
        """Update workspace display"""
        workspace = get_hyprland_workspace()
        self.workspace_label.set_text(workspace)

    def update_time_callback(self) -> bool:
        """Callback for time updates"""
        self.update_time()
        return True  # Continue the timer

    def update_battery_callback(self) -> bool:
        """Callback for battery updates"""
        self.update_battery()
        return True  # Continue the timer

    def update_workspace_callback(self) -> bool:
        """Callback for workspace updates"""
        self.update_workspace()
        return True  # Continue the timer

    def apply_status_bar_styles(self):
        """Apply CSS styling to the status bar"""
        # Style the window
        apply_styles(
            self,
            """
            window {
                background: rgba(20, 20, 20, 0.95);
                border-radius: 8px;
                border: 1px solid #444;
                box-shadow: 0 2px 8px rgba(0,0,0,0.6);
            }
            """
        )

        # Style the main box
        apply_styles(
            self.main_box,
            """
            box {
                background: transparent;
                padding: 8px 16px;
            }
            """
        )

        # Style labels
        label_style = """
            label {
                color: #ffffff;
                font-size: 14px;
                font-weight: 500;
                font-family: monospace;
                text-shadow: 0 1px 2px rgba(0,0,0,0.5);
            }
        """

        apply_styles(self.time_label, label_style)
        apply_styles(self.battery_label, label_style)
        apply_styles(self.workspace_label, label_style)


def on_activate(app: Gtk.Application):
    # Create status bar window
    win = StatusBar(application=app)

    # Try to set up layer shell for status bar (Wayland)
    try:
        GtkLayerShell.init_for_window(win)
        GtkLayerShell.set_layer(win, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.LEFT, True)
        
        # Add some margin from the edges
        GtkLayerShell.set_margin(win, GtkLayerShell.Edge.TOP, 10)
        GtkLayerShell.set_margin(win, GtkLayerShell.Edge.LEFT, 10)
    except Exception as e:
        # Fallback for X11 or when layer shell is not available
        print(f"Layer shell not available, using regular window: {e}")
        # Position window at top-left corner for X11
        try:
            win.set_default_size(300, 40)
        except Exception:
            pass

    win.present()


def main():
    app = Gtk.Application(application_id="com.example.statusbar")
    app.connect("activate", on_activate)

    display = Gdk.Display.get_default()
    if not display:
        sys.exit(1)

    try:
        app.run(None)
    except KeyboardInterrupt:
        sys.exit(0)

    app.connect("shutdown", lambda *_: sys.exit(0))


if __name__ == "__main__":
    main()