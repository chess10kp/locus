# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from gi.repository import Gdk, Gtk, Gio, GioUnix, GLib, Gtk4LayerShell as GtkLayerShell  # pyright: ignore
from typing_extensions import final
import subprocess
import re
import os
import glob
import sys
import contextlib
import shlex
import logging
from pathlib import Path
from typing import Any, Optional, List, Dict

from utils import apply_styles, load_desktop_apps, VBox
from .config import CUSTOM_LAUNCHERS, METADATA, WALLPAPER_DIR, LOCK_PASSWORD
from utils import sanitize_expr, evaluate_calculator
from launchers.lock_launcher import LockScreen

import webbrowser

# Setup Logging
logger = logging.getLogger("AppLauncher")
logging.basicConfig(level=logging.INFO)

# --- GIO Compatibility Patching ---
try:
    from gi.repository import GioUnix
    SystemDesktopAppInfo = GioUnix.DesktopAppInfo
except (ImportError, AttributeError):
    SystemDesktopAppInfo = Gio.DesktopAppInfo

# Fix for older GLib versions where Unix streams might be moved
if not hasattr(Gio, "UnixInputStream") and 'GioUnix' in sys.modules:
    from gi.repository import GioUnix
    Gio.UnixInputStream = getattr(GioUnix, "InputStream", None)
    Gio.UnixOutputStream = getattr(GioUnix, "OutputStream", None)


def fuzzy_match(query, target):
    """Check if query is a fuzzy match for target (case insensitive)."""
    query = query.lower()
    target = target.lower()
    query_idx = 0
    for char in target:
        if query_idx < len(query) and char == query[query_idx]:
            query_idx += 1
    return query_idx == len(query)


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


# --- Core Launching Logic ---

def detach_child() -> None:
    """
    Runs in the child process before execing.
    os.setsid() makes the child a session leader, detaching it from Python.
    """
    os.setsid()

    # Redirect I/O to /dev/null to prevent the child from hanging on parent pipes
    if not sys.stdout.isatty():
        with open(os.devnull, "w+b") as null_fp:
            null_fd = null_fp.fileno()
            for fp in [sys.stdin, sys.stdout, sys.stderr]:
                try:
                    os.dup2(null_fd, fp.fileno())
                except Exception:
                    pass

def launch_detached(cmd: List[str], working_dir: Optional[str] = None) -> None:
    """
    Spawns the process using GLib's async mechanism.
    """
    # Check for systemd-run (the cleanest way to launch on modern Linux)
    use_systemd_run = os.path.exists("/usr/bin/systemd-run")

    final_cmd = cmd
    if use_systemd_run:
        # systemd-run --user puts the app in its own independent cgroup
        final_cmd = ["systemd-run", "--user", "--scope", "--quiet"] + cmd

    # Sanitize Environment
    env = dict(os.environ.items())
    # Critical fix for Rider: Don't force GDK_BACKEND if we aren't sure
    if env.get("GDK_BACKEND") != "wayland":
        env.pop("GDK_BACKEND", None)

    # IMPORTANT: Remove LD_PRELOAD to prevent it from affecting child processes
    # The LD_PRELOAD is only needed for the status bar's layer-shell anchoring
    env.pop("LD_PRELOAD", None)

    try:
        envp = [f"{k}={v}" for k, v in env.items()]
        GLib.spawn_async(
            argv=final_cmd,
            envp=envp,
            flags=GLib.SpawnFlags.SEARCH_PATH_FROM_ENVP | GLib.SpawnFlags.SEARCH_PATH,
            child_setup=None if use_systemd_run else detach_child,
            **({"working_directory": working_dir} if working_dir else {})
        )
        logger.info("Process spawned: %s", " ".join(final_cmd))
    except Exception as e:
        logger.exception('Could not launch "%s": %s', final_cmd, e)

# --- App Info Wrapper ---

class AppLauncher:
    @staticmethod
    def launch_by_desktop_file(desktop_file_path: str, project_path: Optional[str] = None) -> bool:
        """
        Parses a .desktop file and launches the command within.
        """
        app_info = SystemDesktopAppInfo.new_from_filename(desktop_file_path)
        if not app_info:
            logger.error("Could not load desktop file: %s", desktop_file_path)
            return False

        app_exec = app_info.get_commandline()
        if not app_exec:
            return False

        # Clean up field codes (%u, %f, etc)
        app_exec = re.sub(r"\%[uUfFdDnNickvm]", "", app_exec).strip()

        cmd = shlex.split(app_exec)
        if project_path:
            cmd.append(project_path)

        working_dir = app_info.get_string("Path")
        launch_detached(cmd, working_dir)
        return True


def handle_custom_launcher(command: str, apps: List[Dict]) -> bool:
    """
    The main handler to bridge your configuration with the launcher.
    """
    if command not in CUSTOM_LAUNCHERS:
        return False

    launcher = CUSTOM_LAUNCHERS[command]
    target_name = ""

    if isinstance(launcher, str):
        target_name = launcher
    elif isinstance(launcher, dict) and launcher.get("type") == "app":
        target_name = launcher.get("name", "")

    if target_name:
        for app in apps:
            if target_name.lower() in app["name"].lower():
                # 'app["file"]' should be the path to the .desktop file
                return AppLauncher.launch_by_desktop_file(app["file"])

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
                # Clean environment for child processes
                env = dict(os.environ.items())
                env.pop("LD_PRELOAD", None)  # Remove LD_PRELOAD for child processes
                subprocess.Popen(command, shell=True, env=env)
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
        self.METADATA = METADATA
        self.parse_time = parse_time

        # Initialize hook registry before creating launchers
        from .hooks import HookRegistry

        self.hook_registry = HookRegistry()

        from launchers import (
            CalcLauncher,
            BookmarkLauncher,
            BluetoothLauncher,
            MonitorLauncher,
            WallpaperLauncher,
            TimerLauncher,
            KillLauncher,
            MusicLauncher,
            RefileLauncher,
        )

        # Import lock launcher separately since it's not part of the main package

        self.calc_launcher = CalcLauncher(self)
        self.bookmark_launcher = BookmarkLauncher(self)
        self.bluetooth_launcher = BluetoothLauncher(self)
        self.monitor_launcher = MonitorLauncher(self)
        self.wallpaper_launcher = WallpaperLauncher(self)
        self.timer_launcher = TimerLauncher(self)
        self.kill_launcher = KillLauncher(self)
        self.music_launcher = MusicLauncher(self)
        self.refile_launcher = RefileLauncher(self)

        # Lock screen instance (created when needed)
        self.lock_screen = None
        self.wallpaper_loaded = False
        self.timer_remaining = 0
        self.timer_update_id = 0

        # Search entry
        self.search_entry = Gtk.Entry()
        self.search_entry.connect("changed", self.on_search_changed)
        self.search_entry.connect("activate", self.on_entry_activate)
        self.search_entry.set_halign(Gtk.Align.FILL)
        self.search_entry.set_hexpand(True)

        self.selected_row = None
        self.search_entry.set_placeholder_text("Search applications...")

        # Scrolled window for apps
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_vexpand(True)

        # List box for apps
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.scrolled.set_child(self.list_box)

        # Populate list
        self.populate_apps()

        # Main box
        vbox = VBox(spacing=6)
        vbox.append(self.search_entry)
        vbox.append(self.scrolled)
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
                border-width: 0;
                border-style: none;
                outline: none;
                box-shadow: none;
                border-radius: 5px;
                padding: 5px;
                font-size: 16px;
                font-family: Iosevka;
            }
            entry:focus {
                border: none;
                border-width: 0;
                border-style: none;
                outline: none;
                box-shadow: none;
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

    def apply_button_style(self, button):
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

    def create_button_with_metadata(self, main_text, metadata_text="", hook_data=None):
        """Create a button with main text and optional metadata below in smaller font."""
        if metadata_text:
            markup = f"{main_text}\n<span size='smaller' color='#d5c4a1'>{metadata_text}</span>"
            button = Gtk.Button()
            label = Gtk.Label()
            label.set_markup(markup)
            label.set_halign(Gtk.Align.START)
            label.set_valign(Gtk.Align.START)
            label.set_wrap(True)
            label.set_wrap_mode(Gtk.WrapMode.WORD)
            button.set_child(label)
        else:
            # Simple button with just main text
            button = Gtk.Button(label=main_text)
            button.get_child().set_halign(Gtk.Align.START)

        self.apply_button_style(button)

        # Connect click handler that uses hook system
        def on_clicked_wrapper(button):
            # Try hooks first
            if not self.hook_registry.execute_select_hooks(self, hook_data):
                # Fall back to default behavior if no hook handles it
                if hasattr(self, 'default_button_handler') and self.default_button_handler:
                    self.default_button_handler(button, hook_data)
                else:
                    # If no specific handler is defined, just hide the launcher
                    self.hide()

        button.connect("clicked", on_clicked_wrapper)
        return button

    def populate_command_mode(self, command):
        if not command:
            for cmd_name in CUSTOM_LAUNCHERS:
                metadata = METADATA.get(cmd_name, "")
                button = self.create_button_with_metadata(f">{cmd_name}", metadata)
                button.connect("clicked", self.on_command_selected, cmd_name)
                self.list_box.append(button)
            self.current_apps = []
        elif command in CUSTOM_LAUNCHERS:
            launcher = CUSTOM_LAUNCHERS[command]
            if isinstance(launcher, str):
                for app in self.apps:
                    if launcher.lower() in app["name"].lower():
                        metadata = METADATA.get(app["name"], "")
                        button = self.create_button_with_metadata(
                            f"Launch: {app['name']}", metadata
                        )
                        button.connect("clicked", self.on_app_clicked, app)
                        self.current_apps = [app]
                        break
                else:
                    button = self.create_button_with_metadata(f"Run: {launcher}", "")
                    button.connect("clicked", self.on_command_clicked, launcher)
                    self.current_apps = []
            else:
                metadata = METADATA.get(command, "")
                button = self.create_button_with_metadata(
                    f"Launch: {command}", metadata
                )
                button.connect("clicked", self.on_custom_launcher_clicked, command)
                self.current_apps = []
            self.apply_button_style(button)
            self.list_box.append(button)
        else:
            matching = [cmd for cmd in CUSTOM_LAUNCHERS if cmd.startswith(command)]
            if matching:
                for cmd in matching:
                    metadata = METADATA.get(cmd, "")
                    button = self.create_button_with_metadata(f">{cmd}", metadata)
                    button.connect("clicked", self.on_command_selected, cmd)
                    self.list_box.append(button)
                self.current_apps = []
            else:
                button = self.create_button_with_metadata(f"Run: {command}", "")
                button.connect("clicked", self.on_command_clicked, command)
                self.list_box.append(button)
                self.current_apps = []

    def populate_app_mode(self, filter_text):
        self.current_apps = []
        for app in self.apps:
            if not filter_text or fuzzy_match(filter_text, app["name"]):
                self.current_apps.append(app)
                metadata = METADATA.get(app["name"], "")
                button = self.create_button_with_metadata(app["name"], metadata)
                button.connect("clicked", self.on_app_clicked, app)
                self.list_box.append(button)

    def populate_apps(self, filter_text=""):
        while self.list_box.get_first_child():
            self.list_box.remove(self.list_box.get_first_child())

        if filter_text.startswith(">calc") and len(filter_text) > 5:
            self.reset_launcher_size()
            expr = filter_text[5:].strip()
            if expr:
                self.calc_launcher.populate(expr)
        elif filter_text.startswith(">bookmark"):
            self.reset_launcher_size()
            query = filter_text[9:].strip()
            self.bookmark_launcher.populate(query)
        elif filter_text.startswith(">bluetooth"):
            self.reset_launcher_size()
            self.bluetooth_launcher.populate()
        elif filter_text.startswith(">monitor"):
            self.reset_launcher_size()
            self.monitor_launcher.populate()
        elif filter_text.startswith(">wallpaper"):
            self.set_wallpaper_mode_size()
            self.wallpaper_launcher.populate(filter_text)
        elif filter_text.startswith(">timer"):
            self.reset_launcher_size()
            time_str = filter_text[6:].strip()
            self.timer_launcher.populate(time_str)
        elif filter_text.startswith(">kill"):
            self.reset_launcher_size()
            self.kill_launcher.populate()
        elif filter_text.startswith(">music"):
            self.reset_launcher_size()
            self.music_launcher.populate(filter_text[6:].strip())
        elif filter_text.startswith(">refile"):
            self.reset_launcher_size()
            query = filter_text[7:].strip()
            self.refile_launcher.populate(query)
        elif filter_text.startswith(">lock"):
            self.reset_launcher_size()
            self.show_lock_screen()
        elif filter_text.startswith(">"):
            self.reset_launcher_size()
            command = filter_text[1:].strip()
            self.populate_command_mode(command)
        else:
            self.reset_launcher_size()
            self.populate_app_mode(filter_text)

    def on_search_changed(self, entry):
        self.selected_row = None
        self.populate_apps(entry.get_text())

    # App methods
    def launch_app(self, app):
        try:
            desktop_file_path = app["file"]
            # Use the new improved launcher logic
            AppLauncher.launch_by_desktop_file(desktop_file_path)
            print(f"Successfully launched {app['name']}")

        except Exception as e:
            print(f"Failed to launch {app['name']}: {e}")
        self.hide()

    def on_entry_activate(self, entry):
        if self.selected_row:
            button = self.selected_row.get_child()
            if button:
                button.emit("clicked")
                self.hide()
                return

        text = self.search_entry.get_text()

        # Try hooks first
        if self.hook_registry.execute_enter_hooks(self, text):
            return
        if text.startswith(">calc") and len(text) > 5:
            expr = text[5:].strip()
            if expr:
                sanitized = sanitize_expr(expr)
                result, error = evaluate_calculator(sanitized)
                if error:
                    print(f"Calculator error: {error}")
                    # Do not hide, let user correct
                else:
                    self.calc_launcher.on_result_clicked(None, str(result))
        elif text == ">wallpaper":
            # Set the first wallpaper
            wp_dir = WALLPAPER_DIR
            wallpapers = glob.glob(os.path.join(wp_dir, "*"))
            wallpapers = [os.path.basename(w) for w in wallpapers if os.path.isfile(w)]
            if wallpapers:
                sorted_wallpapers = sorted(wallpapers)
                self.wallpaper_launcher.set_wallpaper(sorted_wallpapers[0])
            self.hide()
        elif text == ">wallpaper random":
            self.wallpaper_launcher.on_wallpaper_random(None)
            self.hide()
        elif text == ">wallpaper cycle":
            self.wallpaper_launcher.on_wallpaper_cycle(None)
            self.hide()
        elif text.startswith(">timer "):
            time_str = text[6:].strip()
            self.timer_launcher.start_timer(time_str)
            self.hide()
        elif text == ">lock":
            self.show_lock_screen()
            self.hide()
        elif text.startswith(">"):
            command = text[1:].strip()
            # For built-in commands, don't fall through to shell
            builtin_commands = [
                "calc",
                "bookmark",
                "bluetooth",
                "wallpaper",
                "timer",
                "monitor",
                "kill",
                "music",
                "refile",
                "lock",
            ]
            if command in builtin_commands:
                # This is a built-in command, don't execute as shell
                return
            elif not handle_custom_launcher(command, self.apps):
                if command:
                    self.run_command(command)
        elif self.current_apps:
            self.launch_app(self.current_apps[0])
        else:
            if text:
                self.run_command(text)

    def on_app_clicked(self, button, app):
        self.launch_app(app)

    def on_command_clicked(self, button, command):
        self.run_command(command)

    # Calculator methods

    # Bookmark methods

    # Bluetooth methods

    # Monitor methods

    # Wallpaper methods

    # Timer methods

    # Navigation methods
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

    def set_wallpaper_mode_size(self):
        """Increase launcher size for wallpaper mode to accommodate larger thumbnails."""
        self.set_default_size(1000, 600)

    def reset_launcher_size(self):
        """Reset launcher to default size for non-wallpaper modes."""
        self.set_default_size(600, 400)

    def on_custom_launcher_clicked(self, button, command):
        if handle_custom_launcher(command, self.apps):
            self.hide()

    # Command methods
    def on_command_selected(self, button, command):
        # Set the search entry to >command and trigger activate
        if command in [
            "calc",
            "bookmark",
            "bluetooth",
            "wallpaper",
            "timer",
            "monitor",
            "kill",
            "music",
            "refile",
        ]:
            self.search_entry.set_text(f">{command} ")
        elif command == "lock":
            self.search_entry.set_text(f">{command}")
        else:
            self.search_entry.set_text(f">{command}")
        self.on_entry_activate(self.search_entry)

    def run_command(self, command):
        try:
            # Clean environment for child processes
            env = dict(os.environ.items())
            env.pop("LD_PRELOAD", None)  # Remove LD_PRELOAD for child processes
            subprocess.Popen(command, shell=True, env=env)
        except Exception as e:
            print(f"Failed to run command: {e}")
        self.hide()

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Tab:
            text = self.search_entry.get_text()

            # Try hooks first
            result = self.hook_registry.execute_tab_hooks(self, text)
            if result is not None:
                self.search_entry.set_text(result)
                self.search_entry.set_position(-1)
                return True

            # Fall back to hardcoded logic
            if text.startswith(">"):
                command = text[1:].strip()
                builtin = [
                    "calc",
                    "bookmark",
                    "bluetooth",
                    "wallpaper",
                    "timer",
                    "monitor",
                    "kill",
                    "music",
                    "refile",
                    "lock",
                ]
                all_commands = builtin + list(CUSTOM_LAUNCHERS.keys())
                if not command:
                    # No command yet, complete to first available
                    if all_commands:
                        first_cmd = all_commands[0]
                        suffix = " " if first_cmd in builtin else ""
                        self.search_entry.set_text(f">{first_cmd}{suffix}")
                        self.search_entry.set_position(-1)
                        return True
                else:
                    # Partial command, find matching
                    matching = [cmd for cmd in all_commands if cmd.startswith(command)]
                    if matching:
                        cmd = matching[0]
                        suffix = " " if cmd in builtin else ""
                        self.search_entry.set_text(f">{cmd}{suffix}")
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

    # Window methods
    def on_map(self, widget):
        self.search_entry.grab_focus()

    def animate_slide_in(self):
        current_margin = GtkLayerShell.get_margin(self, GtkLayerShell.Edge.BOTTOM)
        target = 0
        if current_margin < target:
            new_margin = min(target, current_margin + 100)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, new_margin)
            GLib.timeout_add(20, self.animate_slide_in)
        else:
            self.search_entry.grab_focus()
        return False

    def show_launcher(self, center_x=None):
        self.search_entry.set_text("")
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, -400)

        if center_x is not None:
            # Center horizontally by disabling left/right anchors
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
            GtkLayerShell.set_margin(
                self, GtkLayerShell.Edge.LEFT, center_x - self.get_width() // 2
            )
        else:
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, False)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, 0)

        self.present()
        self.animate_slide_in()

    def show_lock_screen(self):
        """Show the lock screen."""
        if self.lock_screen is None:
            self.lock_screen = LockScreen(
                password=LOCK_PASSWORD, application=self.get_application()
            )
        self.lock_screen.lock()
