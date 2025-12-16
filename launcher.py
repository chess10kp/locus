# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: basic
# ruff: ignore

from gi.repository import GLib, Gdk, Gtk, Gtk4LayerShell as GtkLayerShell, GdkPixbuf
from typing_extensions import final
import subprocess
import os
import glob
import random
import re
from utils import apply_styles, load_desktop_apps, VBox
from config import CUSTOM_LAUNCHERS
from calculator import sanitize_expr, evaluate_calculator
from bluetooth import (
    bluetooth_power_on,
    bluetooth_scan_on,
    bluetooth_pairable_on,
    bluetooth_discoverable_on,
    bluetooth_get_devices,
    bluetooth_device_connected,
    bluetooth_toggle_power,
    bluetooth_toggle_scan,
    bluetooth_toggle_pairable,
    bluetooth_toggle_discoverable,
    bluetooth_toggle_connection,
)
from bookmarks import get_bookmarks
import webbrowser


def parse_time(time_str):
    match = re.match(r"^(\d+)([hms])$", time_str)
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        if unit == "h":
            return num * 3600
        elif unit == "m":
            return num * 60
        elif unit == "s":
            return num
    return None


def handle_custom_launcher(command, apps):
    if command not in CUSTOM_LAUNCHERS:
        return False

    launcher = CUSTOM_LAUNCHERS[command]
    if isinstance(launcher, str):
        # Legacy: app name
        for app in apps:
            if launcher.lower() in app["name"].lower():
                subprocess.Popen([app["exec"]], shell=False)
                return True
        # If not found, run as command
        subprocess.Popen(launcher, shell=True)
        return True
    elif isinstance(launcher, dict):
        launcher_type = launcher.get("type")
        if launcher_type == "app":
            app_name = launcher.get("name")
            if app_name:
                for app in apps:
                    if app_name.lower() in app["name"].lower():
                        subprocess.Popen([app["exec"]], shell=False)
                        return True
            return False
        elif launcher_type == "command":
            cmd = launcher.get("cmd")
            if cmd:
                subprocess.Popen(cmd, shell=True)
                return True
        elif launcher_type == "url":
            url = launcher.get("url")
            if url:
                webbrowser.open(url)
                return True
        elif launcher_type == "function":
            func = launcher.get("func")
            if func and callable(func):
                func()
                return True
        elif launcher_type == "builtin":
            # Built-in handlers
            if launcher.get("handler") in [
                "calculator",
                "bookmark",
                "bluetooth",
                "wallpaper",
                "timer",
            ]:
                # Handled separately in populate_apps or on_entry_activate
                return False
    return False


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
class Launcher(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(
            **kwargs,
            title="launcher",
            show_menubar=False,
            child=None,
            default_width=600,
            default_height=400,
            destroy_with_parent=True,
            hide_on_close=True,
            resizable=True,
            visible=False,
        )

        self.apps = load_desktop_apps()

        self.wallpaper_buttons = []
        self.wallpaper_loaded = False

        # Search entry
        self.search_entry = Gtk.Entry()
        self.search_entry.connect("changed", self.on_search_changed)
        self.search_entry.connect("activate", self.on_entry_activate)

        self.selected_row = None
        self.search_entry.set_placeholder_text("Search applications...")

        # Scrolled window for apps
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        # List box for apps
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.set_child(self.list_box)

        # Populate list
        self.populate_apps()

        # Main box
        vbox = VBox(spacing=6)
        vbox.append(self.search_entry)
        vbox.append(scrolled)
        self.set_child(vbox)

        # Handle key presses
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(controller)

        # Grab focus on map
        self.connect("map", self.on_map)

        # Layer shell setup
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, 100)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, 0)

        apply_styles(
            self.search_entry,
            """
            entry {
                background: #0e1418;
                color: #ebdbb2;
                border: none;
                border-radius: 5px;
                padding: 5px;
                font-size: 16px;
                font-family: Iosevka;
            }
        """,
        )

        apply_styles(
            self,
            """
            window {
                background: #0e1418;
                border: none;
                border-radius: 5px;
                padding: 0;
                margin: 0;
            }
        """,
        )

    def populate_apps(self, filter_text=""):
        # Clear existing
        while self.list_box.get_first_child():
            self.list_box.remove(self.list_box.get_first_child())

        if filter_text.startswith(">calc "):
            # Calculator mode
            expr = filter_text[6:].strip()
            sanitized = sanitize_expr(expr)
            result, error = evaluate_calculator(sanitized)
            if error:
                button = Gtk.Button(label=f"Error: {error}")
            else:
                button = Gtk.Button(label=f"Result: {result}")
                button.connect("clicked", self.on_result_clicked, result)
            apply_styles(
                button,
                """
                button {
                    background: #3c3836;
                    color: #ebdbb2;
                    border: none;
                    border-radius: 3px;
                    padding: 10px;
                    font-size: 14px;
                    font-family: Iosevka;
                }
                button:hover {
                    background: #504945;
                }
            """,
            )
            self.list_box.append(button)
            self.current_apps = []  # No apps
        elif filter_text.startswith(">bookmark"):
            # Bookmark mode
            bookmarks = get_bookmarks()
            # Add actions
            actions = ["add", "remove", "replace"]
            all_items = bookmarks + actions
            for item in all_items:
                button = Gtk.Button(label=item)
                if item in bookmarks:
                    button.connect("clicked", self.on_bookmark_clicked, item)
                else:
                    button.connect("clicked", self.on_bookmark_action, item)
                apply_styles(
                    button,
                    """
                    button {
                        background: #3c3836;
                        color: #ebdbb2;
                        border: none;
                        border-radius: 3px;
                        padding: 10px;
                        font-size: 14px;
                        font-family: Iosevka;
                    }
                    button:hover {
                        background: #504945;
                    }
                """,
                )
                self.list_box.append(button)
            self.current_apps = []  # No apps
        elif filter_text.startswith(">bluetooth"):
            # Bluetooth mode
            power_status = "Power: on" if bluetooth_power_on() else "Power: off"
            scan_status = "Scan: on" if bluetooth_scan_on() else "Scan: off"
            pairable_status = (
                "Pairable: on" if bluetooth_pairable_on() else "Pairable: off"
            )
            discoverable_status = (
                "Discoverable: on"
                if bluetooth_discoverable_on()
                else "Discoverable: off"
            )
            devices = bluetooth_get_devices()
            device_items = []
            for mac, name in devices:
                status = (
                    "Connected" if bluetooth_device_connected(mac) else "Disconnected"
                )
                device_items.append(f"{name}: {status} ({mac})")
            all_items = [
                power_status,
                scan_status,
                pairable_status,
                discoverable_status,
            ] + device_items
            for item in all_items:
                button = Gtk.Button(label=item)
                button.connect("clicked", self.on_bluetooth_clicked, item)
                apply_styles(
                    button,
                    """
                    button {
                        background: #3c3836;
                        color: #ebdbb2;
                        border: none;
                        border-radius: 3px;
                        padding: 10px;
                        font-size: 14px;
                        font-family: Iosevka;
                    }
                    button:hover {
                        background: #504945;
                    }
                """,
                )
                self.list_box.append(button)
            self.current_apps = []  # No apps
        elif filter_text.startswith(">wallpaper"):
            wp_dir = os.path.expanduser("~/Pictures/wp/")
            if not os.path.exists(wp_dir):
                button = Gtk.Button(
                    label="Wallpaper directory ~/Pictures/wp/ not found"
                )
                apply_styles(
                    button,
                    """
                    button {
                        background: #3c3836;
                        color: #ebdbb2;
                        border: none;
                        border-radius: 3px;
                        padding: 10px;
                        font-size: 14px;
                        font-family: Iosevka;
                    }
                    button:hover {
                        background: #504945;
                    }
                """,
                )
                self.list_box.append(button)
            elif filter_text == ">wallpaper random":
                button = Gtk.Button(label="Set random wallpaper")
                button.connect("clicked", self.on_wallpaper_random)
                apply_styles(
                    button,
                    """
                    button {
                        background: #3c3836;
                        color: #ebdbb2;
                        border: none;
                        border-radius: 3px;
                        padding: 10px;
                        font-size: 14px;
                        font-family: Iosevka;
                    }
                    button:hover {
                        background: #504945;
                    }
                """,
                )
                self.list_box.append(button)
            elif filter_text == ">wallpaper cycle":
                button = Gtk.Button(label="Cycle wallpaper")
                button.connect("clicked", self.on_wallpaper_cycle)
                apply_styles(
                    button,
                    """
                    button {
                        background: #3c3836;
                        color: #ebdbb2;
                        border: none;
                        border-radius: 3px;
                        padding: 10px;
                        font-size: 14px;
                        font-family: Iosevka;
                    }
                    button:hover {
                        background: #504945;
                    }
                """,
                )
                self.list_box.append(button)
            else:
                # List wallpapers with optional search
                if not self.wallpaper_loaded:
                    wallpapers = glob.glob(os.path.join(wp_dir, "*"))
                    wallpapers = [
                        os.path.basename(w) for w in wallpapers if os.path.isfile(w)
                    ]
                    self.wallpaper_buttons = []
                    for wp in sorted(wallpapers):
                        box = Gtk.Box(
                            orientation=Gtk.Orientation.HORIZONTAL, spacing=10
                        )
                        try:
                            pixbuf = GdkPixbuf.Pixbuf.new_from_file(
                                os.path.join(wp_dir, wp)
                            )
                            aspect_ratio = pixbuf.get_width() / pixbuf.get_height()
                            scaled_width = 120
                            scaled_height = int(scaled_width / aspect_ratio)
                            scaled_buf = pixbuf.scale_simple(
                                scaled_width,
                                scaled_height,
                                GdkPixbuf.InterpType.BILINEAR,
                            )
                            image = Gtk.Image.new_from_pixbuf(scaled_buf)
                        except Exception:
                            image = Gtk.Image()  # Fallback if not image
                        label = Gtk.Label(label=wp)
                        label.set_halign(Gtk.Align.START)
                        box.append(image)
                        box.append(label)
                        button = Gtk.Button()
                        button.set_child(box)
                        button.connect("clicked", self.on_wallpaper_clicked, wp)
                        apply_styles(
                            button,
                            """
                            button {
                                background: #3c3836;
                                color: #ebdbb2;
                                border: none;
                                border-radius: 3px;
                                padding: 10px;
                                font-size: 14px;
                                font-family: Iosevka;
                            }
                            button:hover {
                                background: #504945;
                            }
                        """,
                        )
                        self.wallpaper_buttons.append((button, wp))
                    self.wallpaper_loaded = True
                # Now filter
                search_term = ""
                if filter_text.startswith(">wallpaper "):
                    search_term = filter_text[11:].strip().lower()
                matching = [
                    (btn, wp)
                    for btn, wp in self.wallpaper_buttons
                    if not search_term or search_term in wp.lower()
                ]
                if not matching:
                    msg = (
                        "No wallpapers found"
                        if not search_term
                        else f"No wallpapers match '{search_term}'"
                    )
                    button = Gtk.Button(label=msg)
                    apply_styles(
                        button,
                        """
                        button {
                            background: #3c3836;
                            color: #ebdbb2;
                            border: none;
                            border-radius: 3px;
                            padding: 10px;
                            font-size: 14px;
                            font-family: Iosevka;
                        }
                    """,
                    )
                    self.list_box.append(button)
                else:
                    for btn, _ in matching:
                        self.list_box.append(btn)
            self.current_apps = []  # No apps
        elif filter_text.startswith(">timer"):
            time_str = filter_text[6:].strip()
            if time_str:
                seconds = parse_time(time_str)
                if seconds is not None:
                    button = Gtk.Button(label=f"Set timer for {time_str}")
                    button.connect("clicked", self.on_timer_clicked, time_str)
                else:
                    button = Gtk.Button(label="Invalid time format (e.g., 5m)")
            else:
                button = Gtk.Button(label="Usage: >timer 5m")
            apply_styles(
                button,
                """
                button {
                    background: #3c3836;
                    color: #ebdbb2;
                    border: none;
                    border-radius: 3px;
                    padding: 10px;
                    font-size: 14px;
                    font-family: Iosevka;
                }
                button:hover {
                    background: #504945;
                }
            """,
            )
            self.list_box.append(button)
            self.current_apps = []  # No apps
        elif filter_text.startswith(">"):
            # Command mode
            command = filter_text[1:].strip()
            if not command:
                # Show all available commands
                for cmd_name in CUSTOM_LAUNCHERS:
                    button = Gtk.Button(label=f">{cmd_name}")
                    button.connect("clicked", self.on_command_selected, cmd_name)
                    apply_styles(
                        button,
                        """
                        button {
                            background: #3c3836;
                            color: #ebdbb2;
                            border: none;
                            border-radius: 3px;
                            padding: 10px;
                            font-size: 14px;
                            font-family: Iosevka;
                        }
                        button:hover {
                            background: #504945;
                        }
                    """,
                    )
                    self.list_box.append(button)
                self.current_apps = []  # No apps
            elif command in CUSTOM_LAUNCHERS:
                launcher = CUSTOM_LAUNCHERS[command]
                if isinstance(launcher, str):
                    # Legacy app name
                    for app in self.apps:
                        if launcher.lower() in app["name"].lower():
                            button = Gtk.Button(label=f"Launch: {app['name']}")
                            button.connect("clicked", self.on_app_clicked, app)
                            self.current_apps = [app]  # For enter key
                            break
                    else:
                        button = Gtk.Button(label=f"Run: {launcher}")
                        button.connect("clicked", self.on_command_clicked, launcher)
                        self.current_apps = []  # No apps
                else:
                    # Dict type
                    button = Gtk.Button(label=f"Launch: {command}")
                    button.connect("clicked", self.on_custom_launcher_clicked, command)
                    self.current_apps = []  # No apps
                apply_styles(
                    button,
                    """
                    button {
                        background: #3c3836;
                        color: #ebdbb2;
                        border: none;
                        border-radius: 3px;
                        padding: 10px;
                        font-size: 14px;
                        font-family: Iosevka;
                    }
                    button:hover {
                        background: #504945;
                    }
                """,
                )
                self.list_box.append(button)
            else:
                matching = [cmd for cmd in CUSTOM_LAUNCHERS if cmd.startswith(command)]
                if matching:
                    for cmd in matching:
                        button = Gtk.Button(label=f">{cmd}")
                        button.connect("clicked", self.on_command_selected, cmd)
                        apply_styles(
                            button,
                            """
                            button {
                                background: #3c3836;
                                color: #ebdbb2;
                                border: none;
                                border-radius: 3px;
                                padding: 10px;
                                font-size: 14px;
                                font-family: Iosevka;
                            }
                            button:hover {
                                background: #504945;
                            }
                        """,
                        )
                        self.list_box.append(button)
                    self.current_apps = []  # No apps
                else:
                    # Unknown command, run as shell command
                    button = Gtk.Button(label=f"Run: {command}")
                    button.connect("clicked", self.on_command_clicked, command)
                    apply_styles(
                        button,
                        """
                        button {
                            background: #3c3836;
                            color: #ebdbb2;
                            border: none;
                            border-radius: 3px;
                            padding: 10px;
                            font-size: 14px;
                            font-family: Iosevka;
                        }
                        button:hover {
                            background: #504945;
                        }
                    """,
                    )
                    self.list_box.append(button)
                    self.current_apps = []  # No apps
        else:
            # App mode
            self.current_apps = []
            for app in self.apps:
                if filter_text.lower() in app["name"].lower():
                    self.current_apps.append(app)
                    button = Gtk.Button(label=app["name"])
                    button.connect("clicked", self.on_app_clicked, app)
                    apply_styles(
                        button,
                        """
                        button {
                            background: #3c3836;
                            color: #ebdbb2;
                            border: none;
                            border-radius: 3px;
                            padding: 10px;
                            font-size: 14px;
                            font-family: Iosevka;
                        }
                        button:hover {
                            background: #504945;
                        }
                    """,
                    )
                    self.list_box.append(button)

    def on_search_changed(self, entry):
        self.selected_row = None
        self.populate_apps(entry.get_text())

    def on_entry_activate(self, entry):
        if self.selected_row:
            button = self.selected_row.get_child()
            if button:
                button.emit("clicked")
                self.hide()
                return
        text = self.search_entry.get_text()
        if text.startswith(">calc "):
            expr = text[6:].strip()
            sanitized = sanitize_expr(expr)
            result, error = evaluate_calculator(sanitized)
            if error:
                print(f"Calculator error: {error}")
                # Do not hide, let user correct
            else:
                # Copy to clipboard
                result_str = str(result)  # pyright: ignore
                try:
                    subprocess.run(["wl-copy", result_str], check=True)
                except subprocess.CalledProcessError:
                    try:
                        subprocess.run(
                            ["xclip", "-selection", "clipboard"],
                            input=result_str.encode(),
                            check=True,
                        )
                    except subprocess.CalledProcessError:
                        print(f"Failed to copy to clipboard: {result_str}")
                self.hide()
        elif text == ">wallpaper random":
            self.on_wallpaper_random(None)
            self.hide()
        elif text == ">wallpaper cycle":
            self.on_wallpaper_cycle(None)
            self.hide()
        elif text.startswith(">timer "):
            time_str = text[6:].strip()
            self.start_timer(time_str)
            self.hide()
        elif text.startswith(">"):
            command = text[1:].strip()
            if not handle_custom_launcher(command, self.apps):
                if command:
                    self.run_command(command)
        elif self.current_apps:
            self.launch_app(self.current_apps[0])

    def launch_app(self, app):
        try:
            subprocess.Popen([app["exec"]], shell=False)
        except Exception as e:
            print(f"Failed to launch {app['name']}: {e}")
        self.hide()

    def on_app_clicked(self, button, app):
        self.launch_app(app)

    def on_command_clicked(self, button, command):
        self.run_command(command)

    def on_result_clicked(self, button, result):
        # Copy result to clipboard
        try:
            subprocess.run(["wl-copy", result], check=True)
        except subprocess.CalledProcessError:
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=result.encode(),
                    check=True,
                )
            except subprocess.CalledProcessError:
                print(f"Failed to copy to clipboard: {result}")
        self.hide()

    def on_bookmark_clicked(self, button, bookmark):
        # Open bookmark in browser
        webbrowser.open(bookmark)
        self.hide()

    def on_bookmark_action(self, button, action):
        # For now, just print or do nothing
        print(f"Bookmark action: {action}")
        # Could implement dialogs here for add/remove
        self.hide()

    def on_bluetooth_clicked(self, button, item):
        if item.startswith("Power:"):
            bluetooth_toggle_power()
        elif item.startswith("Scan:"):
            bluetooth_toggle_scan()
        elif item.startswith("Pairable:"):
            bluetooth_toggle_pairable()
        elif item.startswith("Discoverable:"):
            bluetooth_toggle_discoverable()
        else:
            # Device item
            # Extract mac from (mac)
            import re

            match = re.search(r"\(([^)]+)\)", item)
            if match:
                mac = match.group(1)
                bluetooth_toggle_connection(mac)
        # Refresh the menu by re-populating
        self.selected_row = None
        self.populate_apps(">bluetooth")

    def on_wallpaper_clicked(self, button, wp):
        self.set_wallpaper(wp)
        self.hide()

    def on_wallpaper_random(self, button):
        wp_dir = os.path.expanduser("~/Pictures/wp/")
        wallpapers = glob.glob(os.path.join(wp_dir, "*"))
        wallpapers = [w for w in wallpapers if os.path.isfile(w)]
        if wallpapers:
            wp_path = random.choice(wallpapers)
            wp = os.path.basename(wp_path)
            self.set_wallpaper(wp)
        self.hide()

    def on_wallpaper_cycle(self, button):
        wp_dir = os.path.expanduser("~/Pictures/wp/")
        default_link = os.path.join(wp_dir, "defaultwp.jpg")
        if os.path.islink(default_link):
            current = os.readlink(default_link)
            current_base = os.path.basename(current)
            match = re.match(r"(\D+)(\d+)\.(jpg|png)", current_base)
            if match:
                style = match.group(1)
                num = int(match.group(2))
                ext = match.group(3)
                num += 1
                next_file = f"{style}{num}.{ext}"
                next_path = os.path.join(wp_dir, next_file)
                if os.path.exists(next_path):
                    self.set_wallpaper(next_file)
                    self.hide()
                    return
                # Wrap to 1
                first_file = f"{style}1.{ext}"
                first_path = os.path.join(wp_dir, first_file)
                if os.path.exists(first_path):
                    self.set_wallpaper(first_file)
                    self.hide()
                    return
                # Try other ext
                alt_ext = "png" if ext == "jpg" else "jpg"
                alt_file = f"{style}1.{alt_ext}"
                alt_path = os.path.join(wp_dir, alt_file)
                if os.path.exists(alt_path):
                    self.set_wallpaper(alt_file)
                    self.hide()
                    return
        # Fallback to random
        self.on_wallpaper_random(button)

    def on_timer_clicked(self, button, time_str):
        self.start_timer(time_str)
        self.hide()

    def start_timer(self, time_str):
        seconds = parse_time(time_str)
        if seconds is not None:
            GLib.timeout_add_seconds(seconds, self.on_timer_done)
            subprocess.run(["notify-send", "-a", "Timer", f"set for {time_str}"])
        else:
            subprocess.run(["notify-send", "Invalid time format"])

    def on_timer_done(self):
        subprocess.run(["notify-send", "-a", "Timer", "-t", "3000", "timer complete"])
        sound_path = "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"
        subprocess.Popen(["mpv", "--no-video", sound_path])
        return False

    def set_wallpaper(self, wp):
        wp_dir = os.path.expanduser("~/Pictures/wp/")
        wp_path = os.path.join(wp_dir, wp)
        default_link = os.path.join(wp_dir, "defaultwp.jpg")
        if os.path.exists(default_link) or os.path.islink(default_link):
            os.remove(default_link)
        os.symlink(wp_path, default_link)
        # Assume swaybg
        walset = "swaybg -i"
        if walset.startswith("swaybg"):
            # Kill existing swaybg
            try:
                result = subprocess.run(
                    ["pgrep", "swaybg"], capture_output=True, text=True
                )
                if result.returncode == 0:
                    pids = result.stdout.strip().split("\n")
                    for pid in pids:
                        subprocess.run(["kill", pid], check=False)
            except Exception:
                pass
            subprocess.Popen([walset, wp_path])

    def select_next(self):
        if self.selected_row:
            next_row = self.selected_row.get_next_sibling()
            if next_row:
                self.selected_row = next_row
                self.list_box.select_row(next_row)
                button = next_row.get_child()
                if button:
                    button.grab_focus()
        else:
            first_row = self.list_box.get_row_at_index(0)
            if first_row:
                self.selected_row = first_row
                self.list_box.select_row(first_row)
                button = first_row.get_child()
                if button:
                    button.grab_focus()

    def select_prev(self):
        if self.selected_row:
            prev_row = self.selected_row.get_prev_sibling()
            if prev_row:
                self.selected_row = prev_row
                self.list_box.select_row(prev_row)
                button = prev_row.get_child()
                if button:
                    button.grab_focus()
            else:
                # No previous, jump back to input
                self.selected_row = None
                self.list_box.unselect_all()
                self.search_entry.grab_focus()
        else:
            n_items = 0
            row = self.list_box.get_first_child()
            while row:
                n_items += 1
                row = row.get_next_sibling()
            if n_items > 0:
                last_row = self.list_box.get_row_at_index(n_items - 1)
                if last_row:
                    self.selected_row = last_row
                    self.list_box.select_row(last_row)
                    button = last_row.get_child()
                    if button:
                        button.grab_focus()

    def on_custom_launcher_clicked(self, button, command):
        if handle_custom_launcher(command, self.apps):
            self.hide()

    def on_command_selected(self, button, command):
        # Set the search entry to >command and trigger activate
        if command in ["calc", "bookmark", "bluetooth", "wallpaper", "timer"]:
            self.search_entry.set_text(f">{command} ")
        else:
            self.search_entry.set_text(f">{command}")
        self.on_entry_activate(self.search_entry)

    def run_command(self, command):
        try:
            subprocess.Popen(command, shell=True)
        except Exception as e:
            print(f"Failed to run command: {e}")
        self.hide()

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Tab:
            text = self.search_entry.get_text()
            if text.startswith(">"):
                command = text[1:].strip()
                if not command:
                    # No command yet, complete to first available
                    if CUSTOM_LAUNCHERS:
                        first_cmd = next(iter(CUSTOM_LAUNCHERS))
                        self.search_entry.set_text(f">{first_cmd} ")
                        self.search_entry.set_position(-1)
                        return True
                else:
                    # Partial command, find matching
                    for cmd in CUSTOM_LAUNCHERS:
                        if cmd.startswith(command):
                            if cmd in ["calc", "bookmark", "bluetooth", "timer"]:
                                self.search_entry.set_text(f">{cmd} ")
                            else:
                                self.search_entry.set_text(f">{cmd}")
                            self.search_entry.set_position(-1)
                            return True
            elif self.current_apps:
                # App mode, complete to first app
                self.search_entry.set_text(self.current_apps[0]["name"])
                self.search_entry.set_position(-1)
                return True
            return True  # Prevent default tab behavior
        if keyval == Gdk.KEY_n and (state & Gdk.ModifierType.CONTROL_MASK):
            self.select_next()
            return True
        if keyval == Gdk.KEY_p and (state & Gdk.ModifierType.CONTROL_MASK):
            self.select_prev()
            return True
        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        if keyval == Gdk.KEY_c and (state & Gdk.ModifierType.CONTROL_MASK):
            self.hide()
            return True
        return False

    def on_map(self, widget):
        self.search_entry.grab_focus()

    def animate_slide_in(self):
        current_margin = GtkLayerShell.get_margin(self, GtkLayerShell.Edge.BOTTOM)
        target = 0
        if current_margin < target:
            new_margin = min(target, current_margin + 100)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, new_margin)
            GLib.timeout_add(10, self.animate_slide_in)
        else:
            self.search_entry.grab_focus()
        return False

    def show_launcher(self):
        self.search_entry.set_text("")
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, -400)
        self.present()
        self.animate_slide_in()
