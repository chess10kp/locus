# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from gi.repository import (
    Gdk,
    Gtk,
    Gio,
    GioUnix,
    GLib,
    GObject,
    Gtk4LayerShell as GtkLayerShell,
)  # pyright: ignore
from typing_extensions import final
import subprocess
import re
import os
import sys
import shlex
import logging
from typing import Optional, List, Dict

from utils import apply_styles
from utils.app_loader import get_app_loader
from utils.app_tracker import get_app_tracker
from .config import CUSTOM_LAUNCHERS, METADATA, LOCK_PASSWORD
from .search_models import (
    SearchResult,
    ResultType,
    AppSearchResult,
    CommandSearchResult,
    LauncherSearchResult,
    CustomSearchResult,
    LoadingSearchResult,
)
from launchers.lock_launcher import LockScreen


class WrappedSearchResult(GObject.Object):
    """Wrapper to make search results compatible with GObject-based ListStore."""

    def __init__(self, search_result):
        super().__init__()
        self.search_result = search_result

    @property
    def title(self):
        return self.search_result.title

    @property
    def subtitle(self):
        return self.search_result.subtitle

    @property
    def result_type(self):
        return self.search_result.result_type

    @property
    def index(self):
        return self.search_result.index

    @property
    def app(self):
        return getattr(self.search_result, "app", None)

    @property
    def command(self):
        return getattr(self.search_result, "command", None)

    @property
    def hook_data(self):
        return self.search_result.hook_data

    @property
    def action_data(self):
        return self.search_result.action_data


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


# Note: Using  ulauncher's fuzzy match :D


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


def detach_child() -> None:
    """
    Runs in the child process before execing.
    os.setsid() makes the child a session leader, detaching it from Python.
    """
    os.setsid()

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
    def _find_desktop_file_by_name(app_name: str) -> Optional[str]:
        """
        Search for a desktop file by application name in standard directories.
        """
        from pathlib import Path

        # Convert app name to lowercase for case-insensitive matching
        app_name_lower = app_name.lower()

        desktop_dirs = [
            Path.home() / ".local" / "share" / "applications",
            Path("/usr/local/share/applications"),
            Path("/usr/share/applications"),
            Path("/var/lib/flatpak/exports/share/applications"),
            Path("/var/lib/snapd/desktop/applications"),
        ]

        for desktop_dir in desktop_dirs:
            if not desktop_dir.exists():
                continue

            exact_file = desktop_dir / f"{app_name_lower}.desktop"
            if exact_file.exists():
                return str(exact_file)

            try:
                for desktop_file in desktop_dir.glob("*.desktop"):
                    try:
                        # Try to load and check the desktop file name
                        app_info = SystemDesktopAppInfo.new_from_filename(
                            str(desktop_file)
                        )
                        if app_info:
                            file_name = app_info.get_name()
                            if file_name and file_name.lower() == app_name_lower:
                                return str(desktop_file)
                    except Exception:
                        # idk what we do here
                        continue
            except Exception:
                # Skip problematic directories
                continue

        return None

    @staticmethod
    def launch_by_desktop_file(
        desktop_file_path: str,
        project_path: Optional[str] = None,
        fallback_exec: Optional[str] = None,
        fallback_name: Optional[str] = None,
    ) -> bool:
        """
        Parses a .desktop file and launches the command within.
        Falls back to direct execution if desktop file is not available.
        """
        if desktop_file_path and os.path.exists(desktop_file_path):
            app_info = SystemDesktopAppInfo.new_from_filename(desktop_file_path)
            if app_info:
                app_exec = app_info.get_commandline()
                if app_exec:
                    app_exec = re.sub(r"\%[uUfFdDnNickvm]", "", app_exec).strip()
                    cmd = shlex.split(app_exec)
                    if project_path:
                        cmd.append(project_path)
                    working_dir = app_info.get_string("Path")
                    launch_detached(cmd, working_dir)
                    return True
                else:
                    logger.warning(
                        "Desktop file has no executable: %s", desktop_file_path
                    )
            else:
                logger.warning("Could not load desktop file: %s", desktop_file_path)
        else:
            logger.debug(
                "Desktop file path is empty or does not exist: %s", desktop_file_path
            )

        # Fallback: try to find desktop file by searching standard directories
        if fallback_name:
            found_desktop_file = AppLauncher._find_desktop_file_by_name(fallback_name)
            if found_desktop_file:
                logger.info(
                    "Found desktop file for %s: %s", fallback_name, found_desktop_file
                )
                return AppLauncher.launch_by_desktop_file(
                    found_desktop_file, project_path
                )

        if fallback_exec:
            logger.info("Launching %s directly as fallback", fallback_exec)
            cmd = [fallback_exec]
            if project_path:
                cmd.append(project_path)
            launch_detached(cmd)
            return True

        logger.error(
            "Could not launch application - no valid desktop file or executable found"
        )
        return False


BUILTIN_HANDLERS = {}


def register_builtin_handler(name: str, handler_func):
    """Register a builtin launcher handler function."""
    BUILTIN_HANDLERS[name] = handler_func


def handle_custom_launcher(
    command: str, apps: List[Dict], launcher_instance=None
) -> bool:
    """
    The main handler to bridge your configuration with the launcher.
    """
    # Debug logging
    with open("/tmp/locus_debug.log", "a") as f:
        f.write(f"[DEBUG] handle_custom_launcher called with command='{command}'\n")

    if command not in CUSTOM_LAUNCHERS:
        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] Command '{command}' not in CUSTOM_LAUNCHERS\n")
        return False

    launcher = CUSTOM_LAUNCHERS[command]
    target_name = ""

    if isinstance(launcher, str):
        target_name = launcher
    elif isinstance(launcher, dict):
        launcher_type = launcher.get("type")
        if launcher_type == "app":
            target_name = launcher.get("name", "")
        elif launcher_type == "builtin":
            handler_name = launcher.get("handler")
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] Builtin handler '{handler_name}' requested\n")
            if handler_name and handler_name in BUILTIN_HANDLERS:
                # Call the builtin handler with the launcher instance
                if handler_name and handler_name in BUILTIN_HANDLERS:
                    with open("/tmp/locus_debug.log", "a") as f:
                        f.write(f"[DEBUG] Calling builtin handler '{handler_name}'\n")
                    # Call the builtin handler with the launcher instance
                    BUILTIN_HANDLERS[handler_name](launcher_instance)
                    with open("/tmp/locus_debug.log", "a") as f:
                        f.write(f"[DEBUG] Builtin handler '{handler_name}' completed\n")
                    return True
                return False
            else:
                with open("/tmp/locus_debug.log", "a") as f:
                    f.write(f"[DEBUG] No handler found for builtin '{handler_name}'\n")
                return False

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
        from .config import LAUNCHER_CONFIG

        window_config = LAUNCHER_CONFIG["window"]
        super().__init__(
            **kwargs,
            title="launcher",
            show_menubar=window_config["show_menubar"],
            child=None,
            default_width=window_config["default_width"],
            default_height=window_config["default_height"],
            destroy_with_parent=window_config["destroy_with_parent"],
            hide_on_close=window_config["hide_on_close"],
            resizable=window_config["resizable"],
            visible=False,
            modal=window_config["modal"],
            decorated=window_config["decorated"],
        )

        # Store the application instance for lock screen
        self.application = kwargs.get("application")

        # Use the new optimized app loading system
        self._app_loader = get_app_loader()
        self._app_tracker = get_app_tracker()
        self.METADATA = METADATA
        self.parse_time = parse_time

        # Remove button pooling to prevent memory leaks - using direct widget creation
        self.last_search_text = ""  # Cache last search to avoid unnecessary updates

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

        # selected_row is no longer used with ListView
        from .config import LAUNCHER_CONFIG

        self.search_entry.set_placeholder_text(
            LAUNCHER_CONFIG["ui"]["placeholder_text"]
        )
        self.search_timer = None  # For debouncing search
        self._in_search_changed = False  # Guard against recursion
        # Button pooling removed to prevent memory leaks and signal handler conflicts

        # Background loading state
        self.background_loading = False
        self.loading_label = None
        self.loading_start_time = None
        self.destroying = False

        # Timer IDs for cleanup
        self.animation_timer_id = 0
        self.idle_callback_id = 0

        # Scrolled window for apps
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_vexpand(True)

        # Optimized ListView with list recycling
        # Create a simple store that can hold Python objects
        self.list_store = Gio.ListStore()
        self.selection_model = Gtk.SingleSelection.new(self.list_store)
        self.selection_model.set_autoselect(False)
        self.selection_model.set_can_unselect(True)

        self.list_view: Gtk.ListView = Gtk.ListView.new(self.selection_model, None)
        self.list_view.set_vexpand(True)

        # Create factory for rendering items
        self._setup_list_view_factory()

        self.scrolled.set_child(self.list_view)

        # Keep reference to old list_box for compatibility during transition
        self.list_box = None

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

        # Connect to destroy signal for cleanup
        self.connect("destroy", self.on_destroy)

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
                background: #0e1419;
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
                background: #0e1419;
                border: none;
                border-radius: 5px;
                padding: 0;
                margin: 0;
            }
            .hint-label {
                color: #888888;
                font-size: 12px;
                font-family: Iosevka;
            }
        """,
        )

    def _setup_list_view_factory(self):
        """Set up the ListItemFactory for the optimized ListView."""

        def setup_callback(factory, list_item):
            """Called when a new list item widget is created."""
            button = Gtk.Button()
            button.set_hexpand(True)
            button.set_halign(Gtk.Align.FILL)

            # Apply button styling
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

            # Create a horizontal box for content
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            hbox.set_hexpand(True)

            # Text container
            text_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            text_vbox.set_hexpand(True)
            text_vbox.set_halign(Gtk.Align.START)

            # Title label
            title_label = Gtk.Label()
            title_label.set_halign(Gtk.Align.START)
            title_label.set_valign(Gtk.Align.START)
            title_label.set_wrap(True)
            title_label.set_wrap_mode(Gtk.WrapMode.WORD)
            text_vbox.append(title_label)

            # Subtitle label (optional)
            subtitle_label = Gtk.Label()
            subtitle_label.set_halign(Gtk.Align.START)
            subtitle_label.set_valign(Gtk.Align.START)
            subtitle_label.set_wrap(True)
            subtitle_label.set_wrap_mode(Gtk.WrapMode.WORD)
            subtitle_label.add_css_class("dim-label")
            text_vbox.append(subtitle_label)

            # Hint label for Alt+number
            hint_label = Gtk.Label()
            hint_label.set_halign(Gtk.Align.END)
            hint_label.set_hexpand(True)
            hint_label.add_css_class("hint-label")

            hbox.append(text_vbox)
            hbox.append(hint_label)
            button.set_child(hbox)

            # Set child for the list item
            list_item.set_child(button)

            # Store references on the list item for later access
            list_item.button = button
            list_item.title_label = title_label
            list_item.subtitle_label = subtitle_label
            list_item.hint_label = hint_label

        def bind_callback(factory, list_item):
            """Called when a list item needs to display data."""
            search_result = list_item.get_item()
            if not search_result:
                return

            # Get stored references
            button = getattr(list_item, "button", None)
            title_label = getattr(list_item, "title_label", None)
            subtitle_label = getattr(list_item, "subtitle_label", None)
            hint_label = getattr(list_item, "hint_label", None)

            if not all([button, title_label, subtitle_label, hint_label]):
                return

            # Get stored references
            button = getattr(list_item, "button", None)
            title_label = getattr(list_item, "title_label", None)
            subtitle_label = getattr(list_item, "subtitle_label", None)
            hint_label = getattr(list_item, "hint_label", None)

            if not all([button, title_label, subtitle_label, hint_label]):
                return

            # Update title
            if title_label:
                if search_result.subtitle:
                    markup = f"{search_result.title}\n<span size='smaller' color='#d5c4a1'>{search_result.subtitle}</span>"
                    title_label.set_markup(markup)
                else:
                    title_label.set_text(search_result.title)

            # Update subtitle visibility
            if subtitle_label:
                if search_result.subtitle:
                    subtitle_label.set_text(search_result.subtitle)
                    subtitle_label.set_visible(True)
                else:
                    subtitle_label.set_visible(False)

            # Update hint for Alt+number
            if hint_label:
                if (
                    search_result.index is not None
                    and search_result.index > 0
                    and search_result.index <= 9
                ):
                    hint_label.set_text(str(search_result.index))
                    hint_label.set_visible(True)
                else:
                    hint_label.set_visible(False)

            # Update button click handler
            # Remove old handlers to prevent memory leaks
            if button:
                try:
                    if hasattr(button, "clicked_handler_id"):
                        button.disconnect(button.clicked_handler_id)
                except:
                    pass

                # Connect new handler
                button.clicked_handler_id = button.connect(
                    "clicked", self._on_list_item_clicked, search_result
                )

        def unbind_callback(factory, list_item):
            """Called when a list item is no longer displaying data."""
            # Get stored button and clean up signal handlers
            button = getattr(list_item, "button", None)
            if button:
                try:
                    if hasattr(button, "clicked_handler_id"):
                        button.disconnect(button.clicked_handler_id)
                except:
                    pass

        # Create the signal factory
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", setup_callback)
        factory.connect("bind", bind_callback)
        factory.connect("unbind", unbind_callback)

        self.list_view.set_factory(factory)

    def _on_list_item_clicked(self, button, search_result):
        """Handle clicks on list items in the optimized ListView."""
        self.hide()

        if search_result.result_type.name == "APP":
            self.launch_app(search_result.app)
        elif search_result.result_type.name == "COMMAND":
            self.run_command(search_result.command)
        elif search_result.result_type.name == "LAUNCHER":
            # Handle action_data for launchers (e.g., wallpaper file paths)
            if search_result.action_data:
                self.hook_registry.execute_select_hooks(self, search_result.action_data)
            else:
                self.on_command_selected(button, search_result.command)
        elif search_result.result_type.name == "CUSTOM":
            if search_result.hook_data and self.hook_registry:
                self.hook_registry.execute_select_hooks(self, search_result.hook_data)
        elif search_result.result_type.name == "LOADING":
            # Do nothing for loading items
            pass

    @property
    def apps(self):
        """Get apps using the optimized fast loader."""
        return self._app_loader.get_apps()

    def _get_filtered_apps(self, filter_text):
        """Get filtered apps using the new optimized fuzzy search."""
        from .config import LAUNCHER_CONFIG

        max_results = LAUNCHER_CONFIG["search"]["max_results"]

        # Use the new optimized app loader with fuzzy search
        return self._app_loader.search_apps(filter_text, max_results)

    def _clear_listbox(self):
        """Clear all items from the optimized list store."""
        self.list_store.remove_all()

    def _register_launchers(self):
        """Auto-discover and register all launcher modules."""
        try:
            # Import launchers package to trigger auto-registration
            import launchers  # noqa: F401

            # Import all launchers (except lock screen which is handled separately)
            from launchers.music_launcher import MusicLauncher
            from launchers.refile_launcher import RefileLauncher
            from launchers.timer_launcher import TimerLauncher
            from launchers.focus_launcher import FocusLauncher
            from launchers.calc_launcher import CalcLauncher
            from launchers.bookmark_launcher import BookmarkLauncher
            from launchers.bluetooth_launcher import BluetoothLauncher
            from launchers.wallpaper_launcher import WallpaperLauncher
            from launchers.kill_launcher import KillLauncher
            from launchers.shell_launcher import ShellLauncher

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

            focus_launcher = FocusLauncher(self)
            if focus_launcher.name not in self.launcher_registry._launchers:
                self.launcher_registry.register(focus_launcher)

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

            shell_launcher = ShellLauncher(self)
            if shell_launcher.name not in self.launcher_registry._launchers:
                self.launcher_registry.register(shell_launcher)

            # Register builtin handlers
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] Registering 'lock' builtin handler\n")
            register_builtin_handler(
                "lock", lambda launcher_instance: show_lock_screen(launcher_instance)
            )
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] Builtin handlers: {list(BUILTIN_HANDLERS.keys())}\n")

            # Lock screen is handled separately (not a launcher)
            self.lock_screen = None

            # Note: Individual launchers should register themselves in their __init__

        except ImportError as e:
            logger.warning(f"Could not import some launchers: {e}")

    def populate_command_mode(self, command):
        """Show available launchers and custom commands in command mode using optimized ListView."""
        self.current_apps = []

        if not command:
            # Show all available commands
            all_commands = list(CUSTOM_LAUNCHERS.keys())
            for launcher_name, triggers in self.launcher_registry.list_launchers():
                all_commands.extend(triggers)

            index = 1
            for cmd_name in sorted(set(all_commands)):
                if index > 10:  # Show more command results
                    break

                metadata = METADATA.get(cmd_name, "")
                result = LauncherSearchResult(
                    cmd_name, metadata, index if index <= 9 else None
                )
                self.list_store.append(WrappedSearchResult(result))
                index += 1

        elif command in CUSTOM_LAUNCHERS:
            # Handle custom launcher from config
            launcher = CUSTOM_LAUNCHERS[command]
            if isinstance(launcher, str):
                # Try to find matching app
                for app in self.apps:
                    if launcher.lower() in app["name"].lower():
                        metadata = METADATA.get(app["name"], "")
                        result = AppSearchResult(app, 1)
                        self.list_store.append(WrappedSearchResult(result))
                        self.current_apps = [app]
                        break
                else:
                    # No app found, run as command
                    result = CommandSearchResult(launcher, 1)
                    self.list_store.append(WrappedSearchResult(result))
            else:
                metadata = METADATA.get(command, "")
                result = LauncherSearchResult(command, metadata, 1)
                self.list_store.append(WrappedSearchResult(result))

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
                    if index > 10:  # Show more command results
                        break

                    metadata = METADATA.get(cmd, "")
                    result = LauncherSearchResult(
                        cmd, metadata, index if index <= 9 else None
                    )
                    self.list_store.append(WrappedSearchResult(result))
                    index += 1
            else:
                # No matching commands, offer to run as shell command
                result = CommandSearchResult(command, 1)
                self.list_store.append(WrappedSearchResult(result))

    def populate_app_mode(self, filter_text):
        from .config import LAUNCHER_CONFIG

        self.current_apps = []
        index = 1
        max_visible = LAUNCHER_CONFIG["performance"]["max_visible_results"]

        # Use cached filtering for better performance
        filtered_apps = self._get_filtered_apps(filter_text)

        # Show loading indicator if background loading and no results yet
        if not filtered_apps and self.background_loading:
            import time

            elapsed = ""
            if self.loading_start_time:
                elapsed = f" ({time.time() - self.loading_start_time:.1f}s)"

            loading_text = f"{LAUNCHER_CONFIG['ui']['loading_text']}{elapsed}"
            result = LoadingSearchResult(loading_text)
            self.list_store.append(WrappedSearchResult(result))
            return

        # Limit results for performance
        visible_apps = filtered_apps[:max_visible]

        for app in visible_apps:
            self.current_apps.append(app)
            metadata = METADATA.get(app["name"], "")
            result = AppSearchResult(app, index if index <= 9 else None)
            self.list_store.append(WrappedSearchResult(result))
            index += 1

    def populate_apps(self, filter_text=""):
        """Populate the launcher with apps or use registered launchers for commands."""
        from .config import LAUNCHER_CONFIG

        # Don't do anything if launcher is being destroyed
        if self.destroying:
            return

        # Skip if search text hasn't changed significantly
        if filter_text == self.last_search_text:
            return
        self.last_search_text = filter_text

        # Return buttons to pool instead of destroying them
        self._clear_listbox()

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
            if LAUNCHER_CONFIG["performance"]["batch_ui_updates"]:
                # Use idle callback for better responsiveness
                if self.idle_callback_id > 0:
                    GLib.source_remove(self.idle_callback_id)
                self.idle_callback_id = GLib.idle_add(
                    self._populate_app_mode_idle, filter_text
                )
            else:
                self.populate_app_mode(filter_text)

    def _populate_app_mode_idle(self, filter_text):
        """Populate app mode using idle callback for better performance."""
        self.populate_app_mode(filter_text)
        self.idle_callback_id = 0
        return False  # Don't repeat

    def add_launcher_result(
        self,
        title: str,
        subtitle: str = "",
        index: int | None = None,
        result_type: ResultType | None = None,
        action_data=None,
    ):
        """Add a search result from a sublauncher. This replaces create_button_with_metadata."""
        if result_type is None:
            result_type = ResultType.LAUNCHER

        result = LauncherSearchResult(title, subtitle, index)
        result.action_data = action_data
        self.list_store.append(WrappedSearchResult(result))

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
        # Prevent recursive calls that can cause RecursionError
        if self._in_search_changed:
            return

        self._in_search_changed = True
        try:
            from .config import LAUNCHER_CONFIG

            if self.search_timer:
                GLib.source_remove(self.search_timer)

            # Adaptive debouncing: shorter for small queries, longer for complex ones
            text = entry.get_text()
            base_delay = LAUNCHER_CONFIG["search"]["debounce_delay"]

            if len(text) <= 1:
                debounce_delay = min(base_delay, 50)  # Very fast for single character
            elif len(text) <= 3:
                debounce_delay = min(base_delay, 100)  # Fast for short queries
            else:
                debounce_delay = base_delay  # Standard delay for longer queries

            self.search_timer = GLib.timeout_add(
                debounce_delay, self._debounced_populate, text
            )
        finally:
            self._in_search_changed = False

    def _debounced_populate(self, text):
        # selected_row is no longer used with ListView
        self.populate_apps(text)
        self.search_timer = None
        return False

    # App methods
    def launch_app(self, app):
        try:
            desktop_file_path = app["file"]
            # Track app launch for frequency ranking
            app_name = app.get("name", "")
            app_exec = app.get("exec", "")
            if app_name:
                self._app_tracker.increment_app_start(app_name)

            # Use the new improved launcher logic with fallback support
            success = AppLauncher.launch_by_desktop_file(
                desktop_file_path=desktop_file_path,
                fallback_exec=app_exec,
                fallback_name=app_name,
            )

            if success:
                logger.info(f"Successfully launched {app_name}")
            else:
                logger.error(f"Failed to launch {app_name}")

        except Exception as e:
            logger.error(f"Failed to launch {app.get('name', 'unknown')}: {e}")

    def on_entry_activate(self, entry):
        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] on_entry_activate called\n")

        text = self.search_entry.get_text()
        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] Text entered: '{text}'\n")

        self.hide()
        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] Launcher hidden\n")

        # Check if there's a selected item in the ListView
        selected_pos = self.selection_model.get_selected()
        if selected_pos != Gtk.INVALID_LIST_POSITION:
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] Selected item at position {selected_pos}\n")
            search_result = self.list_store.get_item(selected_pos)
            if search_result:
                self._on_list_item_clicked(None, search_result)
                with open("/tmp/locus_debug.log", "a") as f:
                    f.write(f"[DEBUG] List item clicked, returning\n")
            return

        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] No selected item, processing text: '{text}'\n")

        # Try hooks first
        hook_result = self.hook_registry.execute_enter_hooks(self, text)
        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] Hook execution result: {hook_result}\n")
        if hook_result:
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] Hook handled the command, returning\n")
            return

        # Check if any registered launcher can handle this input
        trigger, launcher, query = self.launcher_registry.find_launcher_for_input(text)
        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] Launcher registry: trigger='{trigger}', launcher={launcher}, query='{query}'\n")

        if launcher and launcher.handles_enter():
            # Let the launcher handle the enter key
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] Launcher {launcher} handling enter\n")
            if launcher.handle_enter(query, self):
                with open("/tmp/locus_debug.log", "a") as f:
                    f.write(f"[DEBUG] Launcher handled the command, returning\n")
                return

        # Handle custom launchers from config
        if text.startswith(">"):
            command = text[1:].strip()
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] Command detected: '{command}'\n")

            launcher_names = [name for name, _ in self.launcher_registry.list_launchers()]
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] Registered launchers: {launcher_names}\n")

            if command in launcher_names:
                # This is a registered launcher command, don't execute as shell
                with open("/tmp/locus_debug.log", "a") as f:
                    f.write(f"[DEBUG] Command '{command}' is in registered launchers, returning without calling handle_custom_launcher\n")
                return
            else:
                with open("/tmp/locus_debug.log", "a") as f:
                    f.write(f"[DEBUG] Command '{command}' not in registered launchers, calling handle_custom_launcher\n")
                if not handle_custom_launcher(command, self.apps, self):
                    with open("/tmp/locus_debug.log", "a") as f:
                        f.write(f"[DEBUG] handle_custom_launcher returned False")
                    if command:
                        with open("/tmp/locus_debug.log", "a") as f:
                            f.write(f", running command\n")
                        self.run_command(command)
                    else:
                        with open("/tmp/locus_debug.log", "a") as f:
                            f.write(f"\n")
                else:
                    with open("/tmp/locus_debug.log", "a") as f:
                        f.write(f"[DEBUG] handle_custom_launcher returned True\n")
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
        """Select the next item in the optimized ListView."""
        n_items = self.list_store.get_n_items()
        if n_items == 0:
            return

        current_selected = self.selection_model.get_selected()
        if current_selected == Gtk.INVALID_LIST_POSITION:
            # No selection, select the first item
            self.selection_model.set_selected(0)
        elif current_selected < n_items - 1:
            # Select the next item
            self.selection_model.set_selected(current_selected + 1)

        # Focus the search entry for better UX
        self.search_entry.grab_focus()

    def select_by_index(self, index):
        """Select the item at the given index (0-based) and activate it."""
        n_items = self.list_store.get_n_items()
        if index < 0 or index >= n_items:
            return

        search_result = self.list_store.get_item(index)
        if search_result:
            # Handle the action directly for Alt+number shortcuts
            if search_result.result_type.name == "LAUNCHER":
                self.hide()
                if search_result.action_data:
                    self.hook_registry.execute_select_hooks(
                        self, search_result.action_data
                    )
                else:
                    self.on_command_selected(None, search_result.command)
            else:
                self._on_list_item_clicked(None, search_result)

    def select_prev(self):
        """Select the previous item in the optimized ListView."""
        n_items = self.list_store.get_n_items()
        if n_items == 0:
            return

        current_selected = self.selection_model.get_selected()
        if current_selected == Gtk.INVALID_LIST_POSITION:
            # No selection, focus search entry
            self.search_entry.grab_focus()
        elif current_selected > 0:
            # Select previous item
            self.selection_model.set_selected(current_selected - 1)
            # Focus the search entry for better UX
            self.search_entry.grab_focus()
        else:
            # At first item, jump back to search entry
            self.selection_model.unselect_all()
            self.search_entry.grab_focus()

    def set_wallpaper_mode_size(self):
        """Increase launcher size for wallpaper mode to accommodate larger thumbnails."""
        self.set_default_size(1000, 600)

    def reset_launcher_size(self):
        """Reset launcher to default size for non-wallpaper modes."""
        self.set_default_size(600, 400)

    def on_custom_launcher_clicked(self, button, command):
        if handle_custom_launcher(command, self.apps, self):
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

    def get_application(self):
        """Return the stored application instance."""
        return self.application

    # Window methods
    def on_map(self, widget):
        self.search_entry.grab_focus()

    def on_hide(self, widget):
        from .config import LAUNCHER_CONFIG

        # Cancel any pending timers to prevent lag when hiding
        if self.search_timer:
            GLib.source_remove(self.search_timer)
            self.search_timer = None

        if self.animation_timer_id > 0:
            GLib.source_remove(self.animation_timer_id)
            self.animation_timer_id = 0

        if self.idle_callback_id > 0:
            GLib.source_remove(self.idle_callback_id)
            self.idle_callback_id = 0

        if LAUNCHER_CONFIG["ui"]["clear_input_on_hide"]:
            self.search_entry.set_text("")

    def on_destroy(self, widget):
        """Clean up all resources when the launcher is destroyed."""
        self.destroying = True

        # Cancel any pending operations
        if self.search_timer:
            GLib.source_remove(self.search_timer)
            self.search_timer = None

        if self.animation_timer_id > 0:
            GLib.source_remove(self.animation_timer_id)
            self.animation_timer_id = 0

        if self.idle_callback_id > 0:
            GLib.source_remove(self.idle_callback_id)
            self.idle_callback_id = 0

        # Button pool is no longer used (buttons are destroyed immediately)

        # Search cache is no longer needed with optimized ListView

    def animate_slide_in(self):
        from .config import LAUNCHER_CONFIG

        animation_config = LAUNCHER_CONFIG["animation"]
        if not animation_config["enable_slide_in"]:
            self.search_entry.grab_focus()
            return False

        current_margin = GtkLayerShell.get_margin(self, GtkLayerShell.Edge.BOTTOM)
        target = animation_config["target_margin"]  # Target margin above statusbar

        if current_margin < target:
            new_margin = min(target, current_margin + animation_config["slide_step"])
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, new_margin)
            self.animation_timer_id = GLib.timeout_add(
                animation_config["slide_duration"], self.animate_slide_in
            )
        else:
            self.animation_timer_id = 0  # Animation complete
            if LAUNCHER_CONFIG["ui"]["auto_grab_focus"]:
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


def show_lock_screen(launcher_instance):
    """Show the lock screen."""
    with open("/tmp/locus_debug.log", "a") as f:
        f.write(f"[DEBUG] show_lock_screen called\n")
        f.write(f"[DEBUG] launcher_instance.lock_screen is {launcher_instance.lock_screen}\n")
        f.write(f"[DEBUG] launcher_instance.get_application() = {launcher_instance.get_application()}\n")

    if launcher_instance.lock_screen is None:
        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] Creating new LockScreen with password='{LOCK_PASSWORD}'\n")
        try:
            launcher_instance.lock_screen = LockScreen(
                password=LOCK_PASSWORD, application=launcher_instance.get_application()
            )
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] LockScreen created successfully\n")
        except Exception as e:
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[ERROR] Failed to create LockScreen: {e}\n")
            raise

    with open("/tmp/locus_debug.log", "a") as f:
        f.write(f"[DEBUG] Calling lock_screen.lock()\n")
    try:
        launcher_instance.lock_screen.lock()
        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] lock_screen.lock() completed\n")
    except Exception as e:
        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[ERROR] lock_screen.lock() failed: {e}\n")
        raise
