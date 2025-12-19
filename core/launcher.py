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
import sys
import shlex
import logging
from typing import Optional, List, Dict

from utils import apply_styles
from .config import CUSTOM_LAUNCHERS, METADATA, LOCK_PASSWORD
from launchers.lock_launcher import LockScreen


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
if not hasattr(Gio, "UnixInputStream") and "GioUnix" in sys.modules:
    from gi.repository import GioUnix

    Gio.UnixInputStream = getattr(GioUnix, "InputStream", None)
    Gio.UnixOutputStream = getattr(GioUnix, "OutputStream", None)


def fuzzy_match(query, target):
    """Check if query is a fuzzy match for target (case insensitive)."""
    query = query.lower()
    target = target.lower()
    if not query:
        return True
    if not target:
        return False

    start = 0
    for char in query:
        pos = target.find(char, start)
        if pos == -1:
            return False
        start = pos + 1
    return True


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
            **({"working_directory": working_dir} if working_dir else {}),
        )
        logger.info("Process spawned: %s", " ".join(final_cmd))
    except Exception as e:
        logger.exception('Could not launch "%s": %s', final_cmd, e)


# --- App Info Wrapper ---


class AppLauncher:
    @staticmethod
    def launch_by_desktop_file(
        desktop_file_path: str, project_path: Optional[str] = None
    ) -> bool:
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

        # Lazy load apps - only load when first needed
        self._apps = None
        self._apps_loaded = False
        self.METADATA = METADATA
        self.parse_time = parse_time

        # Initialize hook registry before creating launchers
        from .hooks import HookRegistry
        from .launcher_registry import launcher_registry

        self.hook_registry = HookRegistry()
        self.launcher_registry = launcher_registry

        # Auto-discover and register all launchers
        self._register_launchers()

        # Legacy lock screen support (created when needed)
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
        self.search_timer = None  # For debouncing search
        self.button_pool = []  # Pool of reusable buttons
        self.last_search_text = ""  # Cache last search to avoid unnecessary updates
        self.search_cache = {}  # Cache search results
        self.cache_max_size = 100  # Maximum cache size

        # Background loading state
        self.background_loading = False
        self.loading_label = None

        # Scrolled window for apps
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_vexpand(True)

        # List box for apps
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.scrolled.set_child(self.list_box)

        # Main box
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.append(self.search_entry)
        vbox.append(self.scrolled)
        self.set_child(vbox)

        # Handle key presses
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(controller)

        # Grab focus on map
        self.connect("map", self.on_map)

        # Clear input field when window is hidden
        self.connect("hide", self.on_hide)

        # Layer shell setup
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        # Position above the statusbar (statusbar is 20px high, so use 25px margin)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, 25)
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

    @property
    def apps(self):
        """Lazy load desktop apps only when first accessed."""
        if not self._apps_loaded:
            from utils.utils import load_desktop_apps, load_desktop_apps_background

            # Load cached apps immediately for fast startup
            self._apps = sorted(load_desktop_apps(), key=lambda x: x["name"].lower())
            self._apps_loaded = True

            # Start background loading to refresh cache if needed
            if not self.background_loading:
                self.background_loading = True
                load_desktop_apps_background(self._on_apps_loaded_background)

        return self._apps or []

    def _on_apps_loaded_background(self, apps):
        """Callback called when background loading completes."""
        self.background_loading = False
        # Update apps list with fresh data
        self._apps = sorted(apps, key=lambda x: x["name"].lower())

        # Clear search cache since apps may have changed
        self.search_cache.clear()

        # Refresh current search if launcher is visible
        if self.get_visible():
            current_text = self.search_entry.get_text()
            if current_text:
                self._populate_launcher(current_text)
            else:
                self._populate_launcher("")

    def _get_filtered_apps(self, filter_text):
        """Get filtered apps with caching for performance."""
        if not filter_text:
            return self.apps[:14]  # Return first 14 apps when no filter

        # Check cache first
        if filter_text in self.search_cache:
            return self.search_cache[filter_text]

        # Compute filtered results
        filtered = []
        filter_lower = filter_text.lower()
        for app in self.apps:
            if len(filtered) >= 14:  # Limit results
                break
            if filter_lower in app["name"].lower():
                filtered.append(app)

        # Cache the result
        if len(self.search_cache) >= self.cache_max_size:
            # Remove oldest entry (simple LRU approximation)
            oldest_key = next(iter(self.search_cache))
            del self.search_cache[oldest_key]
        self.search_cache[filter_text] = filtered

        return filtered

    def _get_button_from_pool(self):
        """Get a button from the pool or create a new one if pool is empty."""
        if self.button_pool:
            button = self.button_pool.pop()
            # Reset button state
            button.set_visible(True)
            # Disconnect all existing click handlers to avoid conflicts
            # Note: GTK doesn't provide a direct way to disconnect all handlers,
            # but we can work around this by not reusing handlers
            return button
        else:
            # Create new button
            button = Gtk.Button()
            self.apply_button_style(button)
            return button

    def _return_buttons_to_pool(self):
        """Return all buttons from list_box to the pool."""
        child = self.list_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            if hasattr(child, "get_child") and child.get_child():
                button = child.get_child()
                if button:
                    # Reset button state
                    button.set_visible(False)
                    self.button_pool.append(button)
            self.list_box.remove(child)
            child = next_child

    def _register_launchers(self):
        """Auto-discover and register all launcher modules."""
        try:
            # Import launchers package to trigger auto-registration
            import launchers  # noqa: F401

            # Import all launchers (except lock screen which is handled separately)
            from launchers.music_launcher import MusicLauncher
            from launchers.refile_launcher import RefileLauncher
            from launchers.timer_launcher import TimerLauncher
            from launchers.calc_launcher import CalcLauncher
            from launchers.bookmark_launcher import BookmarkLauncher
            from launchers.bluetooth_launcher import BluetoothLauncher
            from launchers.wallpaper_launcher import WallpaperLauncher
            from launchers.kill_launcher import KillLauncher
            from launchers.lock_launcher import LockScreen  # noqa: F401

            # Register all launchers
            music_launcher = MusicLauncher(self)
            if music_launcher.name not in self.launcher_registry._launchers:
                self.launcher_registry.register(music_launcher)

            refile_launcher = RefileLauncher(self)
            if refile_launcher.name not in self.launcher_registry._launchers:
                self.launcher_registry.register(refile_launcher)

            timer_launcher = TimerLauncher(self)
            if timer_launcher.name not in self.launcher_registry._launchers:
                self.launcher_registry.register(timer_launcher)

            calc_launcher = CalcLauncher(self)
            if calc_launcher.name not in self.launcher_registry._launchers:
                self.launcher_registry.register(calc_launcher)

            bookmark_launcher = BookmarkLauncher(self)
            if bookmark_launcher.name not in self.launcher_registry._launchers:
                self.launcher_registry.register(bookmark_launcher)

            bluetooth_launcher = BluetoothLauncher(self)
            if bluetooth_launcher.name not in self.launcher_registry._launchers:
                self.launcher_registry.register(bluetooth_launcher)

            wallpaper_launcher = WallpaperLauncher(self)
            if wallpaper_launcher.name not in self.launcher_registry._launchers:
                self.launcher_registry.register(wallpaper_launcher)

            kill_launcher = KillLauncher(self)
            if kill_launcher.name not in self.launcher_registry._launchers:
                self.launcher_registry.register(kill_launcher)

            # Lock screen is handled separately (not a launcher)
            self.lock_screen = None

            # Note: Individual launchers should register themselves in their __init__

        except ImportError as e:
            logger.warning(f"Could not import some launchers: {e}")

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

    def create_button_with_metadata(
        self, main_text, metadata_text="", hook_data=None, index=None
    ):
        """Create a button with main text and optional metadata below in smaller font."""
        # Get button from pool
        button = self._get_button_from_pool()

        # Clear existing child if any
        button.set_child(None)

        # Create a horizontal box for text and hint
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        hbox.set_hexpand(True)

        # Left side: main text and metadata
        text_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        text_vbox.set_hexpand(True)
        text_vbox.set_halign(Gtk.Align.START)

        if metadata_text:
            markup = f"{main_text}\n<span size='smaller' color='#d5c4a1'>{metadata_text}</span>"
            label = Gtk.Label()
            label.set_markup(markup)
            label.set_halign(Gtk.Align.START)
            label.set_valign(Gtk.Align.START)
            label.set_wrap(True)
            label.set_wrap_mode(Gtk.WrapMode.WORD)
            text_vbox.append(label)
        else:
            # Simple text
            label = Gtk.Label(label=main_text)
            label.set_halign(Gtk.Align.START)
            label.set_valign(Gtk.Align.START)
            text_vbox.append(label)

        hbox.append(text_vbox)

        # Right side: hint if index is provided
        if index is not None and index < 10:
            hint_label = Gtk.Label(label=str(index))
            hint_label.set_halign(Gtk.Align.END)
            hint_label.set_hexpand(True)
            apply_styles(
                hint_label,
                """
                label {
                    color: #888888;
                    font-size: 12px;
                    font-family: Iosevka;
                }
            """,
            )
            hbox.append(hint_label)

        button.set_child(hbox)

        # Don't connect click handler here - let the caller do it
        # This avoids conflicts when buttons are reused
        return button

    def populate_command_mode(self, command):
        """Show available launchers and custom commands in command mode."""
        if not command:
            # Show all available commands
            all_commands = list(CUSTOM_LAUNCHERS.keys())
            for launcher_name, triggers in self.launcher_registry.list_launchers():
                all_commands.extend(triggers)

                index = 1
                for cmd_name in sorted(set(all_commands)):
                    metadata = METADATA.get(cmd_name, "")
                    button = self.create_button_with_metadata(
                        f">{cmd_name}", metadata, index=index if index <= 9 else None
                    )
                    button.connect("clicked", self.on_command_selected, cmd_name)
                    row = Gtk.ListBoxRow()
                    row.set_child(button)
                    self.list_box.append(row)
                    index += 1
                    if index > 10:  # Show more command results
                        break
            self.current_apps = []

        elif command in CUSTOM_LAUNCHERS:
            # Handle custom launcher from config
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
                        row = Gtk.ListBoxRow()
                        row.set_child(button)
                        self.list_box.append(row)
                        break
                else:
                    button = self.create_button_with_metadata(f"Run: {launcher}", "")
                    button.connect("clicked", self.on_command_clicked, launcher)
                    self.current_apps = []
                    row = Gtk.ListBoxRow()
                    row.set_child(button)
                    self.list_box.append(row)
            else:
                metadata = METADATA.get(command, "")
                button = self.create_button_with_metadata(
                    f"Launch: {command}", metadata
                )
                button.connect("clicked", self.on_custom_launcher_clicked, command)
                self.current_apps = []
            row = Gtk.ListBoxRow()
            row.set_child(button)
            self.list_box.append(row)

        else:
            # Find matching commands
            matching_custom = [
                cmd for cmd in CUSTOM_LAUNCHERS if cmd.startswith(command)
            ]
            matching_launchers = []
            for launcher_name, triggers in self.launcher_registry.list_launchers():
                for trigger in triggers:
                    if trigger.startswith(command):
                        matching_launchers.append(trigger)

            all_matching = sorted(set(matching_custom + matching_launchers))
            if all_matching:
                index = 1
                for cmd in all_matching:
                    metadata = METADATA.get(cmd, "")
                    button = self.create_button_with_metadata(
                        f">{cmd}", metadata, index=index if index <= 9 else None
                    )
                    button.connect("clicked", self.on_command_selected, cmd)
                    row = Gtk.ListBoxRow()
                    row.set_child(button)
                    self.list_box.append(row)
                    index += 1
                    if index > 10:  # Show more command results
                        break
                self.current_apps = []
            else:
                # No matching commands, offer to run as shell command
                button = self.create_button_with_metadata(f"Run: {command}", "")
                button.connect("clicked", self.on_command_clicked, command)
                row = Gtk.ListBoxRow()
                row.set_child(button)
                self.list_box.append(row)
                self.current_apps = []

    def populate_app_mode(self, filter_text):
        self.current_apps = []
        index = 1

        # Use cached filtering for better performance
        filtered_apps = self._get_filtered_apps(filter_text)

        # Show loading indicator if background loading and no results yet
        if not filtered_apps and self.background_loading:
            loading_label = Gtk.Label(label="Loading applications...")
            loading_label.add_css_class("dim-label")
            loading_row = Gtk.ListBoxRow()
            loading_row.set_child(loading_label)
            loading_row.set_selectable(False)
            self.list_box.append(loading_row)
            return

        for app in filtered_apps:
            self.current_apps.append(app)
            metadata = METADATA.get(app["name"], "")
            button = self.create_button_with_metadata(
                app["name"], metadata, index=index if index <= 9 else None
            )
            button.connect("clicked", self.on_app_clicked, app)
            row = Gtk.ListBoxRow()
            row.set_child(button)
            self.list_box.append(row)
            index += 1

    def populate_apps(self, filter_text=""):
        """Populate the launcher with apps or use registered launchers for commands."""
        # Skip if search text hasn't changed significantly
        if filter_text == self.last_search_text:
            return
        self.last_search_text = filter_text

        # Return buttons to pool instead of destroying them
        self._return_buttons_to_pool()

        # Check if any registered launcher can handle this input
        trigger, launcher, query = self.launcher_registry.find_launcher_for_input(
            filter_text
        )

        if launcher:
            # Use the registered launcher
            size_mode, custom_size = launcher.get_size_mode()
            self._apply_size_mode(size_mode, custom_size)
            launcher.populate(query, self)
        elif filter_text.startswith(">"):
            # Command mode but no launcher found - show available commands
            self.reset_launcher_size()
            command = filter_text[1:].strip()
            self.populate_command_mode(command)
        else:
            # Default app search mode
            self.reset_launcher_size()
            self.populate_app_mode(filter_text)

    def _apply_size_mode(self, size_mode, custom_size):
        """Apply the appropriate size mode for the launcher."""
        if size_mode.name == "wallpaper":
            self.set_wallpaper_mode_size()
        elif size_mode.name == "custom" and custom_size:
            width, height = custom_size
            self.set_default_size(width, height)
        else:
            self.reset_launcher_size()

    def on_search_changed(self, entry):
        if self.search_timer:
            GLib.source_remove(self.search_timer)
        self.search_timer = GLib.timeout_add(
            150, self._debounced_populate, entry.get_text()
        )

    def _debounced_populate(self, text):
        self.selected_row = None
        self.populate_apps(text)
        self.search_timer = None
        return False

    # App methods
    def launch_app(self, app):
        try:
            desktop_file_path = app["file"]
            # Use the new improved launcher logic
            AppLauncher.launch_by_desktop_file(desktop_file_path)
            print(f"Successfully launched {app['name']}")

        except Exception as e:
            print(f"Failed to launch {app['name']}: {e}")

    def on_entry_activate(self, entry):
        self.hide()

        if self.selected_row:
            button = self.selected_row.get_child()
            if button:
                button.emit("clicked")
            return

        text = self.search_entry.get_text()

        # Try hooks first
        if self.hook_registry.execute_enter_hooks(self, text):
            return

        # Check if any registered launcher can handle this input
        trigger, launcher, query = self.launcher_registry.find_launcher_for_input(text)

        if launcher and launcher.handles_enter():
            # Let the launcher handle the enter key
            if launcher.handle_enter(query, self):
                return

        # Special case for lock screen (legacy support)
        if text == ">lock":
            self.show_lock_screen()
            return

        # Handle custom launchers from config
        if text.startswith(">"):
            command = text[1:].strip()
            if command in [name for name, _ in self.launcher_registry.list_launchers()]:
                # This is a registered launcher command, don't execute as shell
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

    def select_by_index(self, index):
        """Select the item at the given index (0-based) and activate it."""
        row = self.list_box.get_row_at_index(index)
        if row:
            self.selected_row = row
            self.list_box.select_row(row)
            button = row.get_child()
            if button:
                button.emit("clicked")
                self.hide()

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

    def on_key_pressed(self, controller, keyval, keycode, state):
        # Handle Alt+1 to Alt+9 for selecting items
        if state & Gdk.ModifierType.ALT_MASK:  # Alt key
            if Gdk.KEY_1 <= keyval <= Gdk.KEY_9:
                index = keyval - Gdk.KEY_1  # 0 for 1, 1 for 2, etc.
                self.select_by_index(index)
                return True

        if keyval == Gdk.KEY_Tab:
            text = self.search_entry.get_text()

            # Try hooks first
            result = self.hook_registry.execute_tab_hooks(self, text)
            if result is not None:
                self.search_entry.set_text(result)
                self.search_entry.set_position(-1)
                return True

            # Check if any registered launcher can handle tab completion
            trigger, launcher, query = self.launcher_registry.find_launcher_for_input(
                text
            )
            if launcher and launcher.handles_tab():
                completion = launcher.handle_tab(query, self)
                if completion:
                    # Return the full command with completion
                    self.search_entry.set_text(f">{trigger}{completion}")
                    self.search_entry.set_position(-1)
                    return True

            # Fall back to command completion from registry
            if text.startswith(">"):
                command = text[1:].strip()
                all_commands = self.launcher_registry.get_all_triggers() + list(
                    CUSTOM_LAUNCHERS.keys()
                )
                if not command:
                    # No command yet, complete to first available
                    if all_commands:
                        first_cmd = all_commands[0]
                        is_launcher_trigger = (
                            first_cmd in self.launcher_registry.get_all_triggers()
                        )
                        suffix = " " if is_launcher_trigger else ""
                        self.search_entry.set_text(f">{first_cmd}{suffix}")
                        self.search_entry.set_position(-1)
                        return True
                else:
                    # Partial command, find matching
                    matching = [cmd for cmd in all_commands if cmd.startswith(command)]
                    if matching:
                        cmd = matching[0]
                        is_launcher_trigger = (
                            cmd in self.launcher_registry.get_all_triggers()
                        )
                        suffix = " " if is_launcher_trigger else ""
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

    def on_hide(self, widget):
        self.search_entry.set_text("")

    def animate_slide_in(self):
        current_margin = GtkLayerShell.get_margin(self, GtkLayerShell.Edge.BOTTOM)
        target = 25  # Target margin above statusbar
        if current_margin < target:
            new_margin = min(target, current_margin + 100)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, new_margin)
            GLib.timeout_add(20, self.animate_slide_in)
        else:
            self.search_entry.grab_focus()
        return False

    def show_launcher(self, center_x=None):
        self.search_entry.set_text("")
        self.last_search_text = ""  # Reset search cache
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
        # Populate with initial apps
        self.populate_apps("")
        self.animate_slide_in()

    def show_lock_screen(self):
        """Show the lock screen."""
        if self.lock_screen is None:
            self.lock_screen = LockScreen(
                password=LOCK_PASSWORD, application=self.get_application()
            )
        self.lock_screen.lock()
