#!/usr/bin/env python3
"""
Run only the status bar component
"""

import sys
import os

# Add the current directory to Python path so we can import from main.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import StatusBar, GtkLayerShell, Gtk, Gdk


def on_activate_status_only(app: Gtk.Application):
    # Create status bar window
    status_win = StatusBar(application=app)

    # Set up layer shell for status bar
    GtkLayerShell.init_for_window(status_win)
    GtkLayerShell.set_layer(status_win, GtkLayerShell.Layer.TOP)
    GtkLayerShell.set_anchor(status_win, GtkLayerShell.Edge.TOP, True)
    GtkLayerShell.set_anchor(status_win, GtkLayerShell.Edge.LEFT, True)
    
    # Add some margin from the edges
    GtkLayerShell.set_margin(status_win, GtkLayerShell.Edge.TOP, 10)
    GtkLayerShell.set_margin(status_win, GtkLayerShell.Edge.LEFT, 10)

    status_win.present()


def main():
    app = Gtk.Application(application_id="com.example.statusbar")
    app.connect("activate", on_activate_status_only)

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