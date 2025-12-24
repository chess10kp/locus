# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import logging
import os
import subprocess
from typing import Optional, Dict, Any
from typing_extensions import final

from gi.repository import Gtk, GLib, Gdk, Gio, Gtk4LayerShell as GtkLayerShell
from utils import apply_styles
from utils.app_loader import get_app_loader
from utils.app_tracker import get_app_tracker

from .config import METADATA, LOCK_PASSWORD, LAUNCHER_CONFIG
from .search_models import ResultType
from .process_launcher import AppLauncher, register_builtin_handler, BUILTIN_HANDLERS
from .launcher_ui import LauncherUI
from .launcher_search import LauncherSearch
from .launcher_navigation import LauncherNavigation
from .hooks import HookRegistry
from .launcher_registry import launcher_registry
from .launcher_state import get_launcher_state
from .utils.time_parsing import parse_time
from launchers.lock_launcher import LockScreen

logger = logging.getLogger("Launcher")


@final
class Launcher(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
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
        from .process_launcher import PerformanceMonitor

        self.perf_monitor = PerformanceMonitor()

        # Remove button pooling to prevent memory leaks - using direct widget creation
        self.last_search_text = ""  # Cache last search to avoid unnecessary updates

        # Initialize hook registry before creating launchers
        self.hook_registry = HookRegistry()
        self.launcher_registry = launcher_registry

        # Track active launcher context for hook disambiguation
        self.active_launcher_context = None

        # Initialize helper classes
        self.ui = LauncherUI(self)
        self.search = LauncherSearch(self)
        self.nav = LauncherNavigation(self)

        # Initialize state manager for resume functionality
        self.launcher_state = get_launcher_state()

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
        self.lock_screens = []
        self.wallpaper_loaded = False
        self.timer_remaining = 0
        self.timer_update_id = 0
        self._current_grid_launcher = None  # Track current grid launcher for config

        # Search entry
        self.search_entry = Gtk.Entry()
        self.search_entry.connect("changed", self.search.on_search_changed)
        self.search_entry.connect("activate", self.on_entry_activate)
        self.search_entry.set_halign(Gtk.Align.FILL)
        self.search_entry.set_hexpand(True)

        self.search_entry.set_placeholder_text(
            LAUNCHER_CONFIG["ui"]["placeholder_text"]
        )

        self.search_timer = None  # For debouncing search
        self._in_search_changed = False  # Guard against recursion

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
        self.list_store = Gio.ListStore()
        self.selection_model = Gtk.SingleSelection.new(self.list_store)
        self.selection_model.set_autoselect(False)
        self.selection_model.set_can_unselect(True)

        self.list_view: Gtk.ListView = Gtk.ListView.new(self.selection_model, None)
        self.list_view.set_vexpand(True)

        # Create factory for rendering items
        self.ui.setup_list_view_factory()

        self.scrolled.set_child(self.list_view)

        # Keep reference to old list_box for compatibility during transition
        self.list_box = None
        self.grid_view = None
        self.current_view = None

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

        # Handle key presses on window
        controller = Gtk.EventControllerKey()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect("key-pressed", self.nav.on_key_pressed)
        self.add_controller(controller)

        # Grab focus on map
        self.connect("map", self.on_map)

        # Connect to destroy signal for cleanup
        self.connect("destroy", self.on_destroy)

        # Clear input field when window is hidden
        self.connect("hide", self.on_hide)

        # Layer shell setup
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
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

    @property
    def apps(self):
        """Get apps using the optimized fast loader."""
        return self._app_loader.get_apps()

    def _register_launchers(self):
        """Auto-discover and register all launcher modules."""
        try:
            # Import launchers package to trigger auto-registration
            import launchers  # noqa: F401

            # Import all launchers (except lock screen which is handled separately)
            from launchers.music_launcher import MpdLauncher
            from launchers.refile_launcher import RefileLauncher
            from launchers.timer_launcher import TimerLauncher
            from launchers.brightness_launcher import BrightnessLauncher
            from launchers.focus_launcher import FocusLauncher
            from launchers.calc_launcher import CalcLauncher
            from launchers.bookmark_launcher import BookmarkLauncher
            from launchers.bluetooth_launcher import BluetoothLauncher
            from launchers.wifi_launcher import WifiLauncher
            from launchers.wallpaper_launcher import WallpaperLauncher
            from launchers.kill_launcher import KillLauncher
            from launchers.shell_launcher import ShellLauncher
            from launchers.file_launcher import FileLauncher
            from launchers.clipboard_launcher import ClipboardLauncher
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
            register_launcher_with_check(BrightnessLauncher)
            register_launcher_with_check(FocusLauncher)
            register_launcher_with_check(CalcLauncher)
            register_launcher_with_check(BookmarkLauncher)
            register_launcher_with_check(BluetoothLauncher)
            register_launcher_with_check(WifiLauncher)
            register_launcher_with_check(ClipboardLauncher)
            register_launcher_with_check(WallpaperLauncher)
            register_launcher_with_check(KillLauncher)
            register_launcher_with_check(ShellLauncher)
            register_launcher_with_check(FileLauncher)
            register_launcher_with_check(DmenuLauncher)
            register_launcher_with_check(EmojiLauncher)
            register_launcher_with_check(WebLauncher)
            register_launcher_with_check(GalleryLauncher)
            register_launcher_with_check(LLMLauncher)

            # Register builtin handlers
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Registering 'lock' builtin handler")
            register_builtin_handler(
                "lock", lambda launcher_instance: show_lock_screen(launcher_instance)
            )
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Builtin handlers: {list(BUILTIN_HANDLERS.keys())}")

            # Lock screen is handled separately (not a launcher)
            self.lock_screens = []

            # Note: Individual launchers should register themselves in their __init__

        except ImportError as e:
            logger.warning(f"Could not import some launchers: {e}")

    def launch_app(self, app):
        """Launch an application by its desktop file."""
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
        """Handle Enter key press."""
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
                    f.write("[DEBUG] Launcher hidden\n")
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
                f.write("[DEBUG] Hook handled the command, returning\n")
            return

        self.hide()
        with open("/tmp/locus_debug.log", "a") as f:
            f.write("[DEBUG] Launcher hidden\n")

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
                from .process_launcher import handle_custom_launcher

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
                self.nav.on_command_selected(button, search_result.command)
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

    def run_command(self, command):
        """Run a shell command."""
        try:
            # Clean environment for child processes
            env = dict(os.environ.items())
            env.pop("LD_PRELOAD", None)  # Remove LD_PRELOAD for child processes
            subprocess.Popen(command, shell=True, env=env)
        except Exception:
            pass

    def get_application(self):
        """Return the stored application instance."""
        return self.application

    # Delegation methods for launchers - delegate to search manager
    def add_launcher_result(
        self,
        title: str,
        subtitle: str = "",
        index: int | None = None,
        result_type: ResultType | None = None,
        action_data=None,
        icon_name: str | None = None,
    ):
        """Add a search result from a sublauncher."""
        self.search.add_launcher_result(
            title, subtitle, index, result_type, action_data, icon_name
        )

    def add_wallpaper_result(
        self,
        title: str,
        image_path: str,
        pixbuf=None,
        index: int | None = None,
        action_data=None,
    ):
        """Add a wallpaper search result with image data."""
        self.search.add_wallpaper_result(title, image_path, pixbuf, index, action_data)

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
        self.search.add_grid_result(
            title, image_path, metadata, pixbuf, index, action_data
        )

    def populate_apps(self, filter_text=""):
        """Populate the launcher with apps or use registered launchers for commands.
        Delegates to search manager.
        """
        self.search.populate_apps(filter_text)

    # Window methods
    def on_map(self, widget):
        """Handle window map event."""
        self.search_entry.grab_focus()

    def on_hide(self, widget):
        """Handle window hide event."""
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

        # Save state before clearing (if resume is enabled)
        if LAUNCHER_CONFIG["ui"]["resume_last_session"]:
            search_text = self.search_entry.get_text()
            selected_index = self.selection_model.get_selected()
            # Save state if there's search text or a valid selection
            if search_text.strip() or selected_index != Gtk.INVALID_LIST_POSITION:
                self.launcher_state.save_state(
                    search_text=search_text,
                    selected_index=selected_index,  # Save actual index, including INVALID_LIST_POSITION
                    active_launcher_context=self.active_launcher_context or "apps",
                )

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
        """Animate the slide-in effect for the launcher."""
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

    def resume_launcher(self, center_x=None):
        """Resume launcher with previously saved state."""
        saved = self.launcher_state.load_state()
        if not saved:
            return False

        # Position window first (similar to show_launcher)
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

        # Set the search text (this will trigger populate_apps and restore view)
        self.search_entry.set_text(saved["search_text"])
        self.last_search_text = ""  # Reset cache to force population

        self.present()

        # Restore selection after population completes (use idle callback)
        def restore_selection():
            # Only restore selection if it's a valid index (>= 0)
            if saved["selected_index"] >= 0:
                self.selection_model.set_selected(saved["selected_index"])
            return False

        GLib.idle_add(restore_selection)
        self.animate_slide_in()
        return True

    def show_launcher(self, center_x=None):
        """Show the launcher window."""
        # Try to resume if enabled and state exists
        if LAUNCHER_CONFIG["ui"]["resume_last_session"]:
            if self.resume_launcher(center_x):
                return  # Successfully resumed

        # Fresh start (fallback)
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
        self.search.populate_apps("")
        self.animate_slide_in()


def show_lock_screen(launcher_instance):
    """Show the lock screen on all monitors."""
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("show_lock_screen called")
        logger.debug(
            f"launcher_instance.lock_screens is {launcher_instance.lock_screens}"
        )

    # If already locked, do nothing
    if launcher_instance.lock_screens:
        return

    display = Gdk.Display.get_default()
    if not display:
        if logger.isEnabledFor(logging.ERROR):
            logger.error("No display available for lock screen")
        return

    monitors = display.get_monitors()
    n_monitors = monitors.get_n_items()

    if n_monitors == 0:
        if logger.isEnabledFor(logging.ERROR):
            logger.error("No monitors available for lock screen")
        return

    # Define unlock_all callback
    def unlock_all():
        for lock_screen in launcher_instance.lock_screens:
            lock_screen.hide()
            lock_screen.destroy()
        launcher_instance.lock_screens.clear()
        # Disconnect monitor change handler
        if (
            hasattr(launcher_instance, "monitor_changed_handler_id")
            and launcher_instance.monitor_changed_handler_id
        ):
            monitors.disconnect(launcher_instance.monitor_changed_handler_id)
            launcher_instance.monitor_changed_handler_id = None

    # Create lock screens for each monitor
    for i in range(n_monitors):
        monitor = monitors.get_item(i)
        is_input_enabled = i == 0  # Only first monitor gets input

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Creating LockScreen for monitor {i}, input_enabled={is_input_enabled}"
            )

        try:
            lock_screen = LockScreen(
                password=LOCK_PASSWORD,
                application=launcher_instance.get_application(),
                monitor=monitor,
                is_input_enabled=is_input_enabled,
                unlock_all_callback=unlock_all if is_input_enabled else None,
            )
            launcher_instance.lock_screens.append(lock_screen)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"LockScreen {i} created successfully")
        except Exception as e:
            if logger.isEnabledFor(logging.ERROR):
                logger.error(f"Failed to create LockScreen for monitor {i}: {e}")
            continue

    # Lock all screens
    for i, lock_screen in enumerate(launcher_instance.lock_screens):
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Calling lock_screen.lock() for monitor {i}")
        try:
            lock_screen.lock()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"lock_screen.lock() completed for monitor {i}")
        except Exception as e:
            if logger.isEnabledFor(logging.ERROR):
                logger.error(f"lock_screen.lock() failed for monitor {i}: {e}")

    # Handle monitor changes
    def on_monitors_changed(model, position, removed, added):
        if not launcher_instance.lock_screens:
            return
        # Recreate lock screens for new monitor configuration
        unlock_all()  # Destroy existing
        # Re-call show_lock_screen to recreate
        show_lock_screen(launcher_instance)

    launcher_instance.monitor_changed_handler_id = monitors.connect(
        "items-changed", on_monitors_changed
    )
