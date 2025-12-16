# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: basic
# ruff: ignore

from gi.repository import GLib, Gdk, Gtk, Gtk4LayerShell as GtkLayerShell
from typing_extensions import final
import subprocess

from utils import apply_styles, load_desktop_apps, VBox
from config import CUSTOM_LAUNCHERS
import re
import webbrowser
import os


def bluetooth_power_on():
    try:
        result = subprocess.run(
            ["bluetoothctl", "show"], capture_output=True, text=True, timeout=5
        )
        return "Powered: yes" in result.stdout
    except Exception:
        return False


def bluetooth_scan_on():
    try:
        result = subprocess.run(
            ["bluetoothctl", "show"], capture_output=True, text=True, timeout=5
        )
        return "Discovering: yes" in result.stdout
    except Exception:
        return False


def bluetooth_pairable_on():
    try:
        result = subprocess.run(
            ["bluetoothctl", "show"], capture_output=True, text=True, timeout=5
        )
        return "Pairable: yes" in result.stdout
    except Exception:
        return False


def bluetooth_discoverable_on():
    try:
        result = subprocess.run(
            ["bluetoothctl", "show"], capture_output=True, text=True, timeout=5
        )
        return "Discoverable: yes" in result.stdout
    except Exception:
        return False


def bluetooth_get_devices():
    try:
        result = subprocess.run(
            ["bluetoothctl", "devices"], capture_output=True, text=True, timeout=5
        )
        devices = []
        for line in result.stdout.splitlines():
            if line.startswith("Device "):
                parts = line.split(" ", 2)
                if len(parts) >= 3:
                    mac = parts[1]
                    name = parts[2]
                    devices.append((mac, name))
        return devices
    except Exception:
        return []


def bluetooth_device_connected(mac):
    try:
        result = subprocess.run(
            ["bluetoothctl", "info", mac], capture_output=True, text=True, timeout=5
        )
        return "Connected: yes" in result.stdout
    except Exception:
        return False


def bluetooth_toggle_power():
    if bluetooth_power_on():
        subprocess.run(["bluetoothctl", "power", "off"], timeout=5)
    else:
        subprocess.run(["bluetoothctl", "power", "on"], timeout=5)


def bluetooth_toggle_scan():
    if bluetooth_scan_on():
        subprocess.run(["bluetoothctl", "scan", "off"], timeout=5)
    else:
        subprocess.run(["bluetoothctl", "scan", "on"], timeout=5)


def bluetooth_toggle_pairable():
    if bluetooth_pairable_on():
        subprocess.run(["bluetoothctl", "pairable", "off"], timeout=5)
    else:
        subprocess.run(["bluetoothctl", "pairable", "on"], timeout=5)


def bluetooth_toggle_discoverable():
    if bluetooth_discoverable_on():
        subprocess.run(["bluetoothctl", "discoverable", "off"], timeout=5)
    else:
        subprocess.run(["bluetoothctl", "discoverable", "on"], timeout=5)


def bluetooth_toggle_connection(mac):
    if bluetooth_device_connected(mac):
        subprocess.run(["bluetoothctl", "disconnect", mac], timeout=5)
    else:
        subprocess.run(["bluetoothctl", "connect", mac], timeout=5)


def sanitize_expr(expr):
    """Sanitize and fix common calculator expression errors"""
    # Remove spaces
    expr = expr.replace(" ", "")
    # Fix double operators
    expr = re.sub(r"\+\+", "+", expr)
    expr = re.sub(r"--", "+", expr)
    expr = re.sub(r"\+\-", "-", expr)
    expr = re.sub(r"-\+", "-", expr)
    # Add * for implicit multiplication
    expr = re.sub(r"(\d)\(", r"\1*(", expr)
    expr = re.sub(r"\)(\d)", r")*\1", expr)
    expr = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", expr)  # e.g., 2pi -> 2*pi
    return expr


def evaluate_calculator(expr):
    """Evaluate calculator expression with proper error handling"""
    if not expr.strip():
        return None, "Empty expression"

    if len(expr) > 100:
        return None, "Expression too long"

    # Check for invalid characters (only allow numbers, operators, parentheses, and common math functions)
    allowed_chars = set("0123456789+-*/().eEpiPIcosintaqrtlg")
    if not all(c in allowed_chars for c in expr):
        return None, "Invalid characters in expression"
    # Prevent power operator for safety
    if "**" in expr:
        return None, "Power operator not allowed"

    try:
        # Use a restricted environment for eval
        safe_dict = {
            "__builtins__": {},
            "pi": 3.141592653589793,
            "e": 2.718281828459045,
            "cos": __import__("math").cos,
            "sin": __import__("math").sin,
            "tan": __import__("math").tan,
            "sqrt": __import__("math").sqrt,
            "log": __import__("math").log,
            "lg": __import__("math").log10,
        }
        result = eval(expr, safe_dict)
        if isinstance(result, complex):
            return None, "Complex numbers not supported"
        return str(result), None
    except SyntaxError:
        return None, "Invalid syntax"
    except NameError:
        return None, "Unknown function or variable"
    except ZeroDivisionError:
        return None, "Division by zero"
    except OverflowError:
        return None, "Result too large"
    except ValueError as e:
        if "math domain" in str(e):
            return None, "Math domain error"
        return None, f"Value error: {e}"
    except Exception as e:
        return None, f"Calculation error: {e}"


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

        # Search entry
        self.search_entry = Gtk.Entry()
        self.search_entry.connect("changed", self.on_search_changed)
        self.search_entry.connect("activate", self.on_entry_activate)
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
            bookmark_file = os.path.expanduser("~/.bookmarks")
            bookmarks = []
            if os.path.exists(bookmark_file):
                with open(bookmark_file, "r") as f:
                    bookmarks = [line.strip() for line in f if line.strip()]
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
        self.populate_apps(entry.get_text())

    def on_entry_activate(self, entry):
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
        self.populate_apps(">bluetooth")

    def on_custom_launcher_clicked(self, button, command):
        if handle_custom_launcher(command, self.apps):
            self.hide()

    def on_command_selected(self, button, command):
        # Set the search entry to >command and trigger activate
        if command in ["calc", "bookmark", "bluetooth"]:
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
                            if cmd == "calc":
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
