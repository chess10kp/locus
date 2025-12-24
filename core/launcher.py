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
    GdkPixbuf,
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
import time
import statistics
from typing import Optional, List, Dict, Any

from utils import apply_styles
from utils.app_loader import get_app_loader
from utils.app_tracker import get_app_tracker
from .config import CUSTOM_LAUNCHERS, METADATA, LOCK_PASSWORD, LAUNCHER_CONFIG
from .search_models import (
    SearchResult,
    ResultType,
    AppSearchResult,
    CommandSearchResult,
    LauncherSearchResult,
    CustomSearchResult,
    LoadingSearchResult,
    GridSearchResult,
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

    @property
    def image_path(self):
        return getattr(self.search_result, "image_path", None)

    @property
    def icon_name(self):
        icon_name = getattr(self.search_result, "icon_name", None)
        return icon_name

    @property
    def icon_pixbuf(self):
        pixbuf = getattr(self.search_result, "icon_pixbuf", None)
        return pixbuf

    @icon_pixbuf.setter
    def icon_pixbuf(self, value):
        setattr(self.search_result, "icon_pixbuf", value)

    @property
    def pixbuf(self):
        return getattr(self.search_result, "pixbuf", None)


# Setup Logging
logger = logging.getLogger("AppLauncher")
logging.basicConfig(level=logging.DEBUG)


class PerformanceMonitor:
    """Track search performance statistics for optimization."""

    def __init__(self, window_size: int = 100):
        self.timings: List[Dict] = []
        self.window_size = window_size

    def record(
        self, operation: str, duration_ms: float, query: str = "", result_count: int = 0
    ):
        """Record a performance measurement."""
        self.timings.append(
            {
                "op": operation,
                "time": duration_ms,
                "query": query,
                "results": result_count,
                "ts": time.time(),
            }
        )

        # Keep only recent measurements
        if len(self.timings) > self.window_size:
            self.timings = self.timings[-self.window_size :]

    def get_stats(self) -> Dict:
        """Get performance statistics."""
        search_times = [t["time"] for t in self.timings if t["op"] == "search"]
        if not search_times:
            return {}

        return {
            "count": len(search_times),
            "mean": statistics.mean(search_times),
            "median": statistics.median(search_times),
            "p95": statistics.quantiles(search_times, n=20)[18]
            if len(search_times) > 20
            else max(search_times),
            "max": max(search_times),
            "min": min(search_times),
        }

    def get_slow_searches(self, threshold_ms: float = 50) -> List[Dict]:
        """Get searches that exceeded the threshold."""
        return [
            t for t in self.timings if t["op"] == "search" and t["time"] > threshold_ms
        ]


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
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"handle_custom_launcher called with command='{command}'")

    if command not in CUSTOM_LAUNCHERS:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Command '{command}' not in CUSTOM_LAUNCHERS")
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
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Builtin handler '{handler_name}' requested")
            if handler_name and handler_name in BUILTIN_HANDLERS:
                # Call the builtin handler with the launcher instance
                if handler_name and handler_name in BUILTIN_HANDLERS:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Calling builtin handler '{handler_name}'")
                    # Call the builtin handler with the launcher instance
                    BUILTIN_HANDLERS[handler_name](launcher_instance)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Builtin handler '{handler_name}' completed")
                    return True
                return False
            else:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"No handler found for builtin '{handler_name}'")
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
                pass
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

        # Performance monitoring
        self.perf_monitor = PerformanceMonitor()

        # Remove button pooling to prevent memory leaks - using direct widget creation
        self.last_search_text = ""  # Cache last search to avoid unnecessary updates

        # Initialize hook registry before creating launchers
        from .hooks import HookRegistry
        from .launcher_registry import launcher_registry

        self.hook_registry = HookRegistry()
        self.launcher_registry = launcher_registry

        self.current_apps = []

        # Styles
        self.keyb_badge_style = """
            .badges-box label {
                background-color: #3c3836;
                padding: 4px 8px;
                font-size: 12px;
                font-family: Iosevka;
            }
        """
        self.submit_style = """
        .submit-button {
            background-color: #3c3836;
            border-radius: 0px;
            padding: 4px 8px;
            font-size: 12px;
            font-family: Iosevka;
        }
        """

        # Auto-discover and register all launchers
        self._register_launchers()

        # Legacy lock screen support (created when needed)
        self.lock_screen = None
        self.wallpaper_loaded = False
        self.timer_remaining = 0
        self.timer_update_id = 0
        self._current_grid_launcher = None  # Track current grid launcher for config

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

        # Main box with padding
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        # Search row with entry and button
        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        search_row.append(self.search_entry)
        submit_button = Gtk.Button(label="Launch")
        submit_button.connect("clicked", self.on_entry_activate)
        submit_button.set_name("submit-button")
        submit_button.add_css_class("submit-button")
        apply_styles(submit_button, self.submit_style)
        search_row.append(submit_button)
        vbox.append(search_row)
        # Badges
        badges_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        badges_box.set_halign(Gtk.Align.FILL)
        badges_box.add_css_class("badges-box")
        badges_box.set_name("badges-box")
        enter_label = Gtk.Label(label="Enter: Activate")
        badges_box.append(enter_label)
        apply_styles(
            enter_label,
            self.keyb_badge_style,
        )
        up_label = Gtk.Label(label="↑: Select Previous")
        badges_box.append(up_label)
        apply_styles(
            up_label,
            self.keyb_badge_style,
        )
        down_label = Gtk.Label(label="↓: Select Next")
        badges_box.append(down_label)
        apply_styles(
            down_label,
            self.keyb_badge_style,
        )

        tab_label = Gtk.Label(label="Tab: Tab action")
        badges_box.append(tab_label)
        apply_styles(tab_label, self.keyb_badge_style)
        apply_styles(
            badges_box,
            """
            .badges-box {
                font-size: 12px;
            }
        """,
        )
        vbox.append(badges_box)
        vbox.append(self.scrolled)

        # Footer
        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        footer_box.set_halign(Gtk.Align.FILL)
        footer_box.add_css_class("footer-box")
        footer_box.set_name("footer-box")
        self.footer_label = Gtk.Label(label="Applications")
        self.footer_label.set_halign(Gtk.Align.START)
        self.footer_label.set_hexpand(True)
        self.footer_label.set_name("footer-label")
        footer_box.append(self.footer_label)
        vbox.append(footer_box)

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
        # Anchor to top only for vertical positioning, don't anchor left/right for horizontal centering
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        # Position below the statusbar (20px high statusbar + 20px padding)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, 40)
        # No left/right margins for horizontal centering

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
            self.footer_label,
            """
            .footer-label {
                font-size: 12px;
                padding: 12px 6px;
            }
            .footer-box {
                font-size: 12px;
            }
            .footer-box label {
                background-color: #3c3836;
                padding: 4px 8px;
                font-size: 12px;
                font-family: Iosevka;
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
            .footer-box {
                background-color: #3c3836;
                padding: 4px 8px;
                border-radius: 3px;
                margin-top: 4px;
                font-size: 12px;
            }
            .footer-box label {
                color: #888888;
                font-family: Iosevka;
            }
            .badges-box {
                background-color: #3c3836;
                padding: 2px 8px;
                border-radius: 3px;
                margin-top: 4px;
                font-size: 12px;
            }
            .badges-box label {
                color: #888888;
                font-family: Iosevka;
                padding: 0px 4px;
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
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            hbox.set_hexpand(True)

            # Icon image
            icon_image = Gtk.Image()
            icon_image.set_pixel_size(32)  # Match icon_size from config
            icon_image.set_halign(Gtk.Align.START)
            icon_image.set_valign(Gtk.Align.START)

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

            hbox.append(icon_image)
            hbox.append(text_vbox)
            hbox.append(hint_label)
            button.set_child(hbox)

            # Set child for the list item
            list_item.set_child(button)

            # Store references on the list item for later access
            list_item.button = button
            list_item.icon_image = icon_image
            list_item.title_label = title_label
            list_item.subtitle_label = subtitle_label
            list_item.hint_label = hint_label

        def bind_callback(factory, list_item):
            """Called when a list item needs to display data."""
            search_result = list_item.get_item()
            if not search_result:
                return

            icon_pixbuf = getattr(search_result, "icon_pixbuf", None)

            # Get stored references
            button = getattr(list_item, "button", None)
            icon_image = getattr(list_item, "icon_image", None)
            title_label = getattr(list_item, "title_label", None)
            subtitle_label = getattr(list_item, "subtitle_label", None)
            hint_label = getattr(list_item, "hint_label", None)

            if not all([button, title_label, subtitle_label, hint_label]):
                return

            # Update title with bold element
            if title_label:
                if search_result.subtitle:
                    markup = f"<b>{search_result.title}</b>\n<span size='smaller' color='#928374'>{search_result.subtitle}</span>"
                    title_label.set_markup(markup)
                else:
                    markup = f"<b>{search_result.title}</b>"
                    title_label.set_markup(markup)

            # Hide subtitle label since we're showing everything in the title label
            if subtitle_label:
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

            # Update icon
            if icon_image:
                if icon_pixbuf:
                    icon_image.set_from_pixbuf(icon_pixbuf)
                    icon_image.set_visible(True)
                else:
                    # No icon available, hide the image
                    icon_image.set_visible(False)

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

    def _setup_wallpaper_factory(self):
        """Set up a custom ListItemFactory for wallpaper grid view with images only."""

        def wallpaper_setup_callback(factory, list_item):
            """Called when a new list item widget is created for wallpapers."""
            button = Gtk.Button()
            button.set_hexpand(True)
            button.set_vexpand(True)

            # Apply button styling for wallpaper thumbnails
            apply_styles(
                button,
                """
                button {
                    background: transparent;
                    border: none;
                    border-radius: 3px;
                    padding: 5px;
                }
                button:hover {
                    background: #504945;
                    border-radius: 3px;
                }
            """,
            )

            # Image widget for the thumbnail
            image = Gtk.Image()
            image.set_hexpand(True)
            image.set_vexpand(True)
            image.set_size_request(200, 150)  # Fixed size for wallpaper thumbnails
            image.set_pixel_size(200)

            button.set_child(image)

            # Set child for the list item
            list_item.set_child(button)

            # Store references on the list item for later access
            list_item.button = button
            list_item.image = image

        def wallpaper_bind_callback(factory, list_item):
            """Called when a list item needs to display wallpaper data."""
            search_result = list_item.get_item()
            if not search_result or search_result.result_type.name != "WALLPAPER":
                return

            button = getattr(list_item, "button", None)
            image = getattr(list_item, "image", None)

            if not button or not image:
                return

            # Set the image from the pixbuf (if available) or load from path
            if search_result.pixbuf:
                # Use cached pixbuf
                texture = Gdk.Texture.new_for_pixbuf(search_result.pixbuf)
                image.set_paintable(texture)
            elif search_result.image_path:
                try:
                    # Load image from path
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        search_result.image_path, 200, 150, True
                    )
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                    image.set_paintable(texture)
                except Exception as e:
                    logger.warning(f"Failed to load wallpaper image: {e}")
                    # Set a placeholder
                    image.set_from_icon_name("image-missing")
                    image.set_pixel_size(100)

            # Remove old handler to prevent memory leaks
            if hasattr(button, "clicked_handler_id"):
                try:
                    button.disconnect(button.clicked_handler_id)
                except:
                    pass

            # Connect new handler
            button.clicked_handler_id = button.connect(
                "clicked", self._on_list_item_clicked, search_result
            )

        def wallpaper_unbind_callback(factory, list_item):
            """Called when a list item is no longer displaying data."""
            button = getattr(list_item, "button", None)
            if button:
                try:
                    if hasattr(button, "clicked_handler_id"):
                        button.disconnect(button.clicked_handler_id)
                except:
                    pass

        # Create the signal factory
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", wallpaper_setup_callback)
        factory.connect("bind", wallpaper_bind_callback)
        factory.connect("unbind", wallpaper_unbind_callback)

        return factory

    def _setup_grid_factory(self, grid_config):
        """Set up a custom ListItemFactory for grid view with configurable layout."""

        def grid_setup_callback(factory, list_item):
            """Called when a new list item widget is created for grid view."""
            button = Gtk.Button()
            button.set_hexpand(True)
            button.set_vexpand(True)

            # Apply button styling for grid items
            apply_styles(
                button,
                """
                button {
                    background: #3c3836;
                    color: #ebdbb2;
                    border: none;
                    border-radius: 3px;
                    padding: 5px;
                    margin: 2px;
                }
                button:hover {
                    background: #504945;
                    border-radius: 3px;
                }
            """,
            )

            # Create container based on metadata configuration
            if grid_config.get("show_metadata", True):
                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                vbox.set_hexpand(True)
                vbox.set_vexpand(True)

                # Image widget
                image = Gtk.Image()
                image.set_hexpand(True)
                image.set_vexpand(True)
                image.set_size_request(
                    grid_config.get("item_width", 200),
                    grid_config.get("item_height", 200),
                )

                # Text container for metadata
                text_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
                text_hbox.set_hexpand(True)

                # Title label
                title_label = Gtk.Label()
                title_label.set_halign(Gtk.Align.CENTER)
                title_label.set_valign(Gtk.Align.END)
                title_label.set_wrap(True)
                title_label.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
                title_label.set_max_width_chars(grid_config.get("item_width", 200) // 8)
                title_label.add_css_class("dim-label")

                # Optional metadata label
                metadata_label = Gtk.Label()
                metadata_label.set_halign(Gtk.Align.CENTER)
                metadata_label.set_valign(Gtk.Align.END)
                metadata_label.set_wrap(True)
                metadata_label.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
                metadata_label.set_max_width_chars(
                    grid_config.get("item_width", 200) // 8
                )
                metadata_label.add_css_class("dim-label")

                text_hbox.append(title_label)
                if grid_config.get("metadata_position") == "bottom":
                    text_hbox.append(metadata_label)

                vbox.append(image)
                vbox.append(text_hbox)
                button.set_child(vbox)

                # Store references
                list_item.image = image
                list_item.title_label = title_label
                list_item.metadata_label = metadata_label
            else:
                # Image-only grid
                image = Gtk.Image()
                image.set_hexpand(True)
                image.set_vexpand(True)
                image.set_size_request(
                    grid_config.get("item_width", 200),
                    grid_config.get("item_height", 200),
                )
                button.set_child(image)

                # Store reference
                list_item.image = image

            # Set child for the list item
            list_item.set_child(button)
            list_item.button = button

        def grid_bind_callback(factory, list_item):
            """Called when a list item needs to display grid data."""
            search_result = list_item.get_item()
            if not search_result or search_result.result_type.name != "GRID":
                return

            button = getattr(list_item, "button", None)
            image = getattr(list_item, "image", None)
            title_label = getattr(list_item, "title_label", None)
            metadata_label = getattr(list_item, "metadata_label", None)

            if not button:
                return

            # Set the image from the pixbuf (if available) or load from path
            if image:
                if search_result.pixbuf:
                    # Use cached pixbuf
                    texture = Gdk.Texture.new_for_pixbuf(search_result.pixbuf)
                    image.set_paintable(texture)
                elif search_result.image_path:
                    # Initialize variables for use in except block
                    item_width = grid_config.get("item_width", 200)
                    item_height = grid_config.get("item_height", 200)
                    aspect_ratio = grid_config.get("aspect_ratio", "original")
                    try:
                        # Load image from path with aspect ratio handling

                        if aspect_ratio == "square":
                            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                                search_result.image_path, item_width, item_height, True
                            )
                        elif aspect_ratio == "original":
                            # Load with max dimensions, preserve aspect ratio
                            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                                search_result.image_path, item_width, item_height, True
                            )
                        else:  # fixed
                            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                                search_result.image_path, item_width, item_height, False
                            )

                        texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                        image.set_paintable(texture)
                    except Exception as e:
                        logger.warning(f"Failed to load grid image: {e}")
                        # Set a placeholder
                        image.set_from_icon_name("image-missing")
                        image.set_pixel_size(min(item_width, item_height) // 2)

            # Update text labels
            if title_label:
                title_label.set_text(search_result.title)
                title_label.set_visible(True)

            if metadata_label and grid_config.get("metadata_position") == "bottom":
                metadata_text = ""
                if search_result.grid_metadata:
                    # Format metadata as a compact string
                    metadata_parts = []
                    for key, value in search_result.grid_metadata.items():
                        if isinstance(value, (int, float)):
                            metadata_parts.append(f"{key}: {value}")
                        elif value:
                            metadata_parts.append(str(value))
                    metadata_text = " • ".join(metadata_parts[:2])  # Limit to 2 items

                if metadata_text:
                    metadata_label.set_text(metadata_text)
                    metadata_label.set_visible(True)
                else:
                    metadata_label.set_visible(False)

            # Remove old handler to prevent memory leaks
            if hasattr(button, "clicked_handler_id"):
                try:
                    button.disconnect(button.clicked_handler_id)
                except:
                    pass

            # Connect new handler
            button.clicked_handler_id = button.connect(
                "clicked", self._on_list_item_clicked, search_result
            )

        def grid_unbind_callback(factory, list_item):
            """Called when a list item is no longer displaying data."""
            button = getattr(list_item, "button", None)
            if button:
                try:
                    if hasattr(button, "clicked_handler_id"):
                        button.disconnect(button.clicked_handler_id)
                except:
                    pass

        # Create the signal factory
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", grid_setup_callback)
        factory.connect("bind", grid_bind_callback)
        factory.connect("unbind", grid_unbind_callback)

        return factory

    def set_wallpaper_factory(self):
        """Switch to wallpaper-specific factory for image grid view."""
        factory = self._setup_wallpaper_factory()
        self.list_view.set_factory(factory)

        # Switch to list view if needed
        try:
            current_child = self.scrolled.get_child()
            if self.grid_view and current_child == self.grid_view:
                # Unparent the current grid view
                self.grid_view.unparent()
                self.scrolled.set_child(self.list_view)
                self.current_view = self.list_view
        except Exception:
            # If there's an error, ensure we're using list view
            if hasattr(self, "list_view"):
                self.scrolled.set_child(self.list_view)
                self.current_view = self.list_view

    def set_grid_factory(self, grid_config):
        """Switch to grid factory for grid view with configurable layout."""
        # Create GridView if not exists
        if self.grid_view is None:
            self.grid_view = Gtk.GridView.new(self.selection_model)
            self.grid_view.set_vexpand(True)
            self.grid_view.set_max_columns(grid_config.get("columns", 4))

        # Set factory for grid
        factory = self._setup_grid_factory(grid_config)
        self.grid_view.set_factory(factory)

        # Switch to grid view
        try:
            current_child = self.scrolled.get_child()
            if current_child == self.list_view:
                self.list_view.unparent()
                self.scrolled.set_child(self.grid_view)
                self.current_view = self.grid_view
            elif current_child != self.grid_view:
                self.scrolled.set_child(self.grid_view)
                self.current_view = self.grid_view
        except Exception:
            # Fallback - ensure grid view is set
            self.scrolled.set_child(self.grid_view)
            self.current_view = self.grid_view

    def set_default_factory(self):
        """Switch back to default factory for text-based results."""
        # Recreate the default factory
        self._setup_list_view_factory()

        # Switch back to list view if needed
        try:
            current_child = self.scrolled.get_child()
            if self.grid_view and current_child == self.grid_view:
                # Unparent the current grid view
                self.grid_view.unparent()
                self.scrolled.set_child(self.list_view)
                self.current_view = self.list_view

        except Exception:
            # Fallback - ensure list view is set
            if hasattr(self, "grid_view") and self.grid_view:
                self.scrolled.set_child(self.list_view)
                self.current_view = self.list_view

    @property
    def apps(self):
        """Get apps using the optimized fast loader."""
        return self._app_loader.get_apps()

    def _get_filtered_apps(self, filter_text):
        """Get filtered apps using the new optimized fuzzy search."""
        from .config import LAUNCHER_CONFIG

        max_results = LAUNCHER_CONFIG["search"]["max_results"]

        # Track search performance
        start_time = time.time()

        # Use the new optimized app loader with fuzzy search
        results = self._app_loader.search_apps(filter_text, max_results)

        # Record performance
        duration_ms = (time.time() - start_time) * 1000
        self.perf_monitor.record("search", duration_ms, filter_text, len(results))

        # Log slow searches
        if duration_ms > 50:
            logger.warning(
                f"Slow search '{filter_text}': {duration_ms:.2f}ms ({len(results)} results)"
            )

        return results

    def _clear_listbox(self):
        """Clear all items from the optimized list store."""
        self.list_store.remove_all()

    def _register_launchers(self):
        """Auto-discover and register all launcher modules."""
        try:
            # Import launchers package to trigger auto-registration
            import launchers  # noqa: F401

            # Import all launchers (except lock screen which is handled separately)
            from launchers.music_launcher import MpdLauncher
            from launchers.refile_launcher import RefileLauncher
            from launchers.timer_launcher import TimerLauncher
            from launchers.focus_launcher import FocusLauncher
            from launchers.calc_launcher import CalcLauncher
            from launchers.bookmark_launcher import BookmarkLauncher
            from launchers.bluetooth_launcher import BluetoothLauncher
            from launchers.wifi_launcher import WifiLauncher
            from launchers.wallpaper_launcher import WallpaperLauncher
            from launchers.kill_launcher import KillLauncher
            from launchers.shell_launcher import ShellLauncher
            from launchers.file_launcher import FileLauncher
            from launchers.dmenu_launcher import DmenuLauncher
            from launchers.emoji_launcher import EmojiLauncher
            from launchers.gallery_launcher import GalleryLauncher
            from launchers.web_launcher import WebLauncher
            from launchers.llm_launcher import LLMLauncher
            # Notification launcher disabled for now
            # from launchers.notification_launcher import NotificationLauncher

            # Helper function to register launcher with dependency check
            def register_launcher_with_check(LauncherClass):
                """Register a launcher only if its dependencies are met."""
                # Check if launcher has check_dependencies method
                if hasattr(LauncherClass, "check_dependencies"):
                    available, error = LauncherClass.check_dependencies()
                    if not available:
                        logger.info(f"Skipping {LauncherClass.__name__}: {error}")
                        return
                # Create and register the launcher
                launcher = LauncherClass(self)
                if launcher.name not in self.launcher_registry._launchers:
                    self.launcher_registry.register(launcher)

            # Register all launchers with dependency checks
            register_launcher_with_check(MpdLauncher)
            register_launcher_with_check(RefileLauncher)
            register_launcher_with_check(TimerLauncher)
            register_launcher_with_check(FocusLauncher)
            register_launcher_with_check(CalcLauncher)
            register_launcher_with_check(BookmarkLauncher)
            register_launcher_with_check(BluetoothLauncher)
            register_launcher_with_check(WifiLauncher)
            register_launcher_with_check(WallpaperLauncher)
            register_launcher_with_check(KillLauncher)
            register_launcher_with_check(ShellLauncher)
            register_launcher_with_check(FileLauncher)
            register_launcher_with_check(DmenuLauncher)
            register_launcher_with_check(EmojiLauncher)
            register_launcher_with_check(WebLauncher)
            register_launcher_with_check(GalleryLauncher)
            register_launcher_with_check(LLMLauncher)

            # Notification launcher disabled for now
            # notification_launcher = NotificationLauncher(self)
            # if notification_launcher.name not in self.launcher_registry._launchers:
            #     self.launcher_registry.register(notification_launcher)

            # Register builtin handlers
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Registering 'lock' builtin handler")
            register_builtin_handler(
                "lock", lambda launcher_instance: show_lock_screen(launcher_instance)
            )
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Builtin handlers: {list(BUILTIN_HANDLERS.keys())}")

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
                    cmd_name, metadata, index if index <= 9 else 0
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
                        cmd, metadata, index if index <= 9 else 0
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
            result = AppSearchResult(app, index if index <= 9 else 0)
            self.list_store.append(WrappedSearchResult(result))
            index += 1

        # Add web search fallback if no apps matched and it's plain text (not a command)
        if (
            not self.list_store.get_n_items()
            and filter_text
            and not filter_text.startswith(">")
            and not self.launcher_registry._is_custom_prefix_trigger(filter_text)[0]
        ):
            hook_data = {"type": "web_search", "query": filter_text}
            result = LauncherSearchResult(
                command=f"Search web for '{filter_text}'",
                metadata="Press Enter to search",
                index=1,
                action_data=hook_data,
                prefix=False,  # Don't add ">" prefix since it's not a command
            )
            self.list_store.append(WrappedSearchResult(result))
            # Auto-select the web search since it's the only result
            self.selection_model.set_selected(0)

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

        # Check if any registered launcher can handle this input
        trigger, launcher, query = self.launcher_registry.find_launcher_for_input(
            filter_text
        )

        # Update footer based on mode
        if launcher:
            self.footer_label.set_text(launcher.name.capitalize())
        # Check if it's a traditional command with > prefix
        elif filter_text.startswith(">"):
            command = filter_text[1:].strip()
            if command:
                self.footer_label.set_text(f"Command: {command}")
            else:
                self.footer_label.set_text("Commands")
        # Check if it's a custom trigger (has colon or matching trigger)
        else:
            trigger, _ = self.launcher_registry._is_custom_prefix_trigger(filter_text)
            if trigger:
                self.footer_label.set_text(f"Launcher: {trigger}")
            else:
                self.footer_label.set_text("Applications")

        # IMPORTANT: Set factory BEFORE clearing the listbox
        if launcher:
            size_mode, custom_size = launcher.get_size_mode()
            # Store current launcher reference for grid mode
            if size_mode.name == "grid":
                self._current_grid_launcher = launcher
            else:
                self._current_grid_launcher = None
            self._apply_size_mode(size_mode, custom_size)
        # Set default factory if no launcher found
        elif filter_text.startswith(">"):
            self._current_grid_launcher = None
            self.reset_launcher_size()
            self.set_default_factory()
        else:
            trigger, _ = self.launcher_registry._is_custom_prefix_trigger(filter_text)
            if not trigger:
                self._current_grid_launcher = None
                self.reset_launcher_size()
                self.set_default_factory()

        # Return buttons to pool instead of destroying them
        self._clear_listbox()

        if launcher:
            # Use the registered launcher
            launcher.populate(query, self)
        elif filter_text.startswith(">"):
            # Command mode but no launcher found - show available commands
            command = filter_text[1:].strip()
            self.populate_command_mode(command)
        else:
            # Default app search mode
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
        icon_name: str | None = None,
    ):
        """Add a search result from a sublauncher. This replaces create_button_with_metadata."""
        if result_type is None:
            result_type = ResultType.LAUNCHER

        # Don't prefix launcher results with ">" since they're items within a launcher
        safe_index = 0 if index is None else index
        result = LauncherSearchResult(
            title,
            subtitle,
            safe_index,
            action_data=action_data,
            prefix=False,
            icon_name=icon_name,
        )
        self.list_store.append(WrappedSearchResult(result))

    def add_wallpaper_result(
        self,
        title: str,
        image_path: str,
        pixbuf=None,
        index: int | None = None,
        action_data=None,
    ):
        """Add a wallpaper search result with image data."""
        from .search_models import WallpaperSearchResult

        result = WallpaperSearchResult(
            title,
            image_path,
            pixbuf=pixbuf,
            index=index if index else 0,
            action_data=action_data,
        )
        self.list_store.append(WrappedSearchResult(result))

    def add_grid_result(
        self,
        title: str,
        image_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        pixbuf=None,
        index: int | None = None,
        action_data=None,
    ):
        """Add a grid search result with optional image and metadata."""
        result = GridSearchResult(
            title=title,
            image_path=image_path,
            metadata=metadata,
            pixbuf=pixbuf,
            index=index if index is not None else 0,
            action_data=action_data,
        )
        self.list_store.append(WrappedSearchResult(result))

    def _apply_size_mode(self, size_mode, custom_size):
        """Apply the appropriate size mode for the launcher."""
        if size_mode.name == "wallpaper":
            self.set_wallpaper_mode_size()
            self.set_wallpaper_factory()
        elif size_mode.name == "grid":
            # Grid mode - get grid config from launcher
            launcher = None  # Need to get the current launcher instance
            # Find the current launcher that triggered grid mode
            if hasattr(self, "_current_grid_launcher") and self._current_grid_launcher:
                launcher = self._current_grid_launcher
                grid_config = launcher.get_grid_config()
                if grid_config and custom_size:
                    width, height = custom_size
                    self.set_default_size(width, height)
                elif grid_config:
                    # Calculate size based on grid config
                    columns = grid_config.get("columns", 3)
                    item_width = grid_config.get("item_width", 200)
                    item_height = grid_config.get("item_height", 200)
                    spacing = grid_config.get("spacing", 10)
                    total_width = (columns * item_width) + ((columns + 1) * spacing)
                    total_height = (4 * item_height) + (5 * spacing)  # Max 4 rows
                    self.set_default_size(total_width, total_height)
                # Set grid factory with config
                self.set_grid_factory(grid_config)
            else:
                # Fallback to default if no launcher available
                self.reset_launcher_size()
                self.set_default_factory()
        elif size_mode.name == "custom" and custom_size:
            width, height = custom_size
            self.set_default_size(width, height)
            # Center the launcher horizontally for custom sizes
            screen = Gdk.Display.get_default().get_monitor_at_surface(
                self.get_surface()
            )
            if screen:
                monitor_geometry = screen.get_geometry()
                center_x = monitor_geometry.width // 2
                GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
                GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
                GtkLayerShell.set_margin(
                    self, GtkLayerShell.Edge.LEFT, center_x - width // 2
                )
            self.set_default_factory()
        else:
            self.reset_launcher_size()
            self.set_default_factory()

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
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("on_entry_activate called")

        text = self.search_entry.get_text()
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Text entered: '{text}'")

        self.hide()
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Launcher hidden")

        # Check if there's a selected item in the ListView
        selected_pos = self.selection_model.get_selected()
        if selected_pos != Gtk.INVALID_LIST_POSITION:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Selected item at position {selected_pos}")
            search_result = self.list_store.get_item(selected_pos)
            if search_result:
                self.hide()
                with open("/tmp/locus_debug.log", "a") as f:
                    f.write(f"[DEBUG] Launcher hidden\n")
                self._on_list_item_clicked(None, search_result)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("List item clicked, returning")
            return

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"No selected item, processing text: '{text}'")

        # Special case: if typing ">bookmark" and no selection, activate first bookmark
        if text == ">bookmark" and self.list_store.get_n_items() > 0:
            search_result = self.list_store.get_item(0)
            if search_result:
                self._on_list_item_clicked(None, search_result)
            return

        # FAST PATH: Skip hooks for desktop launcher mode if enabled
        if (
            LAUNCHER_CONFIG["behavior"]["desktop_launcher_fast_path"]
            and self.current_apps
            and not text.startswith(">")
            and not self.launcher_registry._is_custom_prefix_trigger(text)[0]
            and not self.launcher_registry.find_launcher_for_input(text)[0]
        ):
            # Directly launch first app result without hook processing
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Taking fast path - launching first app directly")
            self.launch_app(self.current_apps[0])
            return

        # Try hooks first before hiding
        hook_result = self.hook_registry.execute_enter_hooks(self, text)
        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] Hook execution result: {hook_result}\n")
        if hook_result:
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] Hook handled the command, returning\n")
            return

        self.hide()
        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] Launcher hidden\n")

        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] No selected item, processing text: '{text}'\n")

        # Try hooks first
        hook_result = self.hook_registry.execute_enter_hooks(self, text)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Hook execution result: {hook_result}")
        if hook_result:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Hook handled the command, returning")
            return

        # Check if any registered launcher can handle this input
        trigger, launcher, query = self.launcher_registry.find_launcher_for_input(text)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Launcher registry: trigger='{trigger}', launcher={launcher}, query='{query}'"
            )

        if launcher and launcher.handles_enter():
            # Let the launcher handle the enter key
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Launcher {launcher} handling enter")
            if launcher.handle_enter(query, self):
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("Launcher handled the command, returning")
                return

        # Handle custom launchers from config
        # Check for traditional > prefix OR custom triggers
        if text.startswith(">"):
            command = text[1:].strip()
        else:
            # Check for custom trigger
            trigger, prefix_type = self.launcher_registry._is_custom_prefix_trigger(
                text
            )
            if trigger:
                # Extract command part after trigger
                if prefix_type == "colon":
                    command = text[len(trigger) + 1 :].strip()
                else:  # space
                    command = text[len(trigger) + 1 :].strip()
            else:
                command = None

        if command is not None:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Command detected: '{command}'")

            launcher_names = [
                name for name, _ in self.launcher_registry.list_launchers()
            ]
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Registered launchers: {launcher_names}")

            if command in launcher_names:
                # This is a registered launcher command, don't execute as shell
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"Command '{command}' is in registered launchers, returning without calling handle_custom_launcher"
                    )
                return
            else:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"Command '{command}' not in registered launchers, calling handle_custom_launcher"
                    )
                if not handle_custom_launcher(command, self.apps, self):
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("handle_custom_launcher returned False")
                    if command:
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(", running command")
                        self.run_command(command)
                    else:
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("")
                else:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("handle_custom_launcher returned True")
        elif self.current_apps:
            self.launch_app(self.current_apps[0])
        else:
            if text:
                self.run_command(text)

    def on_app_clicked(self, button, app):
        self.launch_app(app)

    def on_command_clicked(self, button, command):
        self.run_command(command)

    def _on_list_item_clicked(self, button, search_result):
        """Handle clicks on list items in both ListView and GridView."""
        print(
            f"_on_list_item_clicked: result_type={search_result.result_type.name}, action_data={search_result.action_data}"
        )
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
        elif search_result.result_type.name == "WALLPAPER":
            # Handle wallpaper selection
            if search_result.action_data:
                self.hook_registry.execute_select_hooks(self, search_result.action_data)
        elif search_result.result_type.name == "GRID":
            # Handle grid item selection
            if search_result.action_data:
                self.hook_registry.execute_select_hooks(self, search_result.action_data)
        elif search_result.result_type.name == "CUSTOM":
            if search_result.hook_data and self.hook_registry:
                self.hook_registry.execute_select_hooks(self, search_result.hook_data)
        elif search_result.result_type.name == "LOADING":
            # Do nothing for loading items
            pass

    def _on_list_item_activated(self, list_view, position):
        """Handle activation of list items (e.g., single-click or Enter)."""
        search_result = self.list_store.get_item(position)
        if search_result:
            self._on_list_item_clicked(None, search_result)

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
        new_position = current_selected

        if current_selected == Gtk.INVALID_LIST_POSITION:
            # No selection, select the first item
            new_position = 0
            self.selection_model.set_selected(0)
        elif current_selected < n_items - 1:
            # Select the next item
            new_position = current_selected + 1
            self.selection_model.set_selected(new_position)

        if new_position != Gtk.INVALID_LIST_POSITION:
            self.list_view.scroll_to(new_position, Gtk.ListScrollFlags.NONE)

        self.search_entry.grab_focus()
        self.search_entry.set_position(-1)

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

    def yank_by_index(self, index):
        """Yank (copy) the item at the given index (0-based) to clipboard."""
        n_items = self.list_store.get_n_items()
        if index < 0 or index >= n_items:
            return

        search_result = self.list_store.get_item(index)
        if search_result:
            # Determine what text to copy based on result type
            text_to_copy = None

            if search_result.result_type.name == "APP":
                # For apps, copy the app name
                text_to_copy = search_result.title
            elif search_result.result_type.name == "COMMAND":
                # For commands, copy the command text (remove "Run: " prefix)
                if search_result.title.startswith("Run: "):
                    text_to_copy = search_result.title[5:]
                else:
                    text_to_copy = search_result.title
            elif search_result.result_type.name == "LAUNCHER":
                # For launchers, copy the launcher command (e.g., ">music")
                text_to_copy = search_result.title
            elif search_result.result_type.name == "CUSTOM":
                # For custom results, copy the title
                text_to_copy = search_result.title

            if text_to_copy:
                # Copy to clipboard
                from utils.clipboard import copy_to_clipboard

                success = copy_to_clipboard(text_to_copy)

                if success:
                    # Close the launcher window after yanking
                    self.hide()
                    # Show brief feedback
                    self._show_yank_feedback(text_to_copy)
                else:
                    pass

    def _show_yank_feedback(self, text: str, duration_ms: int = 500):
        """Show brief feedback when text is yanked to clipboard.

        Args:
            text: The text that was yanked
            duration_ms: How long to show the feedback
        """
        # Truncate text if too long
        display_text = text if len(text) <= 40 else text[:37] + "..."

        # Show feedback in the search entry temporarily
        original_text = self.search_entry.get_text()
        placeholder_text = self.search_entry.get_placeholder_text()

        # Set the search entry to show yanked text
        self.search_entry.set_text(f"Yanked: {display_text}")
        self.search_entry.set_editable(False)

        # Restore original state after duration
        def restore_search_entry():
            self.search_entry.set_editable(True)
            self.search_entry.set_text(original_text)
            if placeholder_text:
                self.search_entry.set_placeholder_text(placeholder_text)

        # Schedule restoration
        GLib.timeout_add(duration_ms, restore_search_entry)

    def select_prev(self):
        """Select the previous item in the optimized ListView."""
        n_items = self.list_store.get_n_items()
        if n_items == 0:
            return

        current_selected = self.selection_model.get_selected()
        new_position = current_selected

        if current_selected == Gtk.INVALID_LIST_POSITION:
            # No selection, focus search entry
            self.search_entry.grab_focus()
            self.search_entry.set_position(-1)
        elif current_selected > 0:
            # Select previous item
            new_position = current_selected - 1
            self.selection_model.set_selected(new_position)
            # Scroll to the selected item to ensure it's visible (like arrow keys do)
            self.list_view.scroll_to(new_position, Gtk.ListScrollFlags.NONE)
            # Focus the search entry for better UX
            self.search_entry.grab_focus()
            self.search_entry.set_position(-1)
        else:
            # At first item, jump back to search entry
            self.selection_model.unselect_all()
            self.search_entry.grab_focus()
            self.search_entry.set_position(-1)

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
            "wifi",
            "wallpaper",
            "timer",
            "kill",
            "mpd",
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
            pass

    def on_key_pressed(self, controller, keyval, keycode, state):
        # Handle Alt+1 to Alt+9 for selecting items
        if state & Gdk.ModifierType.ALT_MASK:  # Alt key
            if Gdk.KEY_1 <= keyval <= Gdk.KEY_9:
                index = keyval - Gdk.KEY_1  # 0 for 1, 1 for 2, etc.
                self.select_by_index(index)
                return True

        # Handle Ctrl+1 to Ctrl+9 for yanking (copying) items
        if state & Gdk.ModifierType.CONTROL_MASK:  # Ctrl key
            if Gdk.KEY_1 <= keyval <= Gdk.KEY_9:
                index = keyval - Gdk.KEY_1  # 0 for 1, 1 for 2, etc.
                self.yank_by_index(index)
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
        if keyval == Gdk.KEY_j and (state & Gdk.ModifierType.CONTROL_MASK):
            self.select_next()
            return True
        if keyval == Gdk.KEY_k and (state & Gdk.ModifierType.CONTROL_MASK):
            self.select_prev()
            return True
        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        if keyval == Gdk.KEY_c and (state & Gdk.ModifierType.CONTROL_MASK):
            self.hide()
            return True
        if keyval == Gdk.KEY_Up:
            self.select_prev()
            return True
        if keyval == Gdk.KEY_Down:
            self.select_next()
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
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("show_lock_screen called")
        logger.debug(
            f"launcher_instance.lock_screen is {launcher_instance.lock_screen}"
        )
        logger.debug(
            f"launcher_instance.get_application() = {launcher_instance.get_application()}"
        )

    if launcher_instance.lock_screen is None:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Creating new LockScreen with password='{LOCK_PASSWORD}'")
        try:
            launcher_instance.lock_screen = LockScreen(
                password=LOCK_PASSWORD, application=launcher_instance.get_application()
            )
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("LockScreen created successfully")
        except Exception as e:
            if logger.isEnabledFor(logging.ERROR):
                logger.error(f"Failed to create LockScreen: {e}")
            raise

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Calling lock_screen.lock()")
    try:
        launcher_instance.lock_screen.lock()
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("lock_screen.lock() completed")
    except Exception as e:
        if logger.isEnabledFor(logging.ERROR):
            logger.error(f"lock_screen.lock() failed: {e}")
        raise
