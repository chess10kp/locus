# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")

from gi.repository import GLib, Gdk, Gtk, Gtk4LayerShell as GtkLayerShell  # pyright: ignore
from typing_extensions import final
import hashlib
import logging


def apply_styles(widget, css: str):
    """Apply CSS styles to a GTK widget."""
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode())
    context = widget.get_style_context()
    context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def VBox(spacing: int = 6, hexpand: bool = False, vexpand: bool = False):
    """Create a vertical GTK Box."""
    return Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=spacing,
        hexpand=hexpand,
        vexpand=vexpand,
    )


def get_monitor_geometry_for_window(window):
    """Get the geometry of the monitor that the window is on."""
    if not window:
        return get_monitor_geometry()

    display = Gdk.Display.get_default()
    if display:
        # Get the surface for the window
        surface = window.get_surface()
        if surface:
            monitor = display.get_monitor_at_surface(surface)
            if monitor:
                return monitor.get_geometry()

        # Fallback to primary monitor or first monitor
        if hasattr(display, "get_primary_monitor"):
            # X11
            monitor = display.get_primary_monitor()
            if monitor:
                return monitor.get_geometry()
        elif hasattr(display, "get_monitors"):
            # Wayland - get the first monitor
            monitors = display.get_monitors()
            if monitors and monitors.get_n_items() > 0:
                monitor = monitors.get_item(0)
                if monitor:
                    return monitor.get_geometry()

    return None


def get_monitor_geometry():
    """Get the geometry of the primary monitor (fallback function)."""
    display = Gdk.Display.get_default()
    if display:
        # Handle both Wayland and X11
        if hasattr(display, "get_primary_monitor"):
            # X11
            monitor = display.get_primary_monitor()
            if monitor:
                return monitor.get_geometry()
        elif hasattr(display, "get_monitors"):
            # Wayland - get the first monitor
            monitors = display.get_monitors()
            if monitors and monitors.get_n_items() > 0:
                monitor = monitors.get_item(0)
                if monitor:
                    return monitor.get_geometry()

    # Final fallback to common resolution
    return None


# Lock screen logger
logger = logging.getLogger("LockScreen")


@final
class LockScreen(Gtk.ApplicationWindow):
    def __init__(
        self,
        password="admin",
        monitor=None,
        is_input_enabled=True,
        unlock_all_callback=None,
        **kwargs,
    ):
        # Use a common resolution initially, will be adjusted in lock()
        width = 1920
        height = 1080

        super().__init__(
            **kwargs,
            title="lock-screen",
            show_menubar=False,
            child=None,
            default_width=width,
            default_height=height,
            destroy_with_parent=True,
            hide_on_close=False,
            resizable=False,
            visible=False,
        )

        self.correct_password_hash = hashlib.sha256(password.encode()).hexdigest()
        self.attempts = 0
        self.max_attempts = 3
        self.monitor = monitor  # Assigned monitor
        self.is_input_enabled = is_input_enabled
        self.unlock_all_callback = unlock_all_callback

        # Create main container
        self.main_box = VBox(spacing=20)
        self.main_box.set_valign(Gtk.Align.FILL)
        self.main_box.set_halign(Gtk.Align.FILL)

        # Create center container for lock UI
        self.center_box = VBox(spacing=20)
        self.center_box.set_valign(Gtk.Align.CENTER)
        self.center_box.set_halign(Gtk.Align.CENTER)

        if self.is_input_enabled:
            # Password entry
            self.password_entry = Gtk.Entry()
            self.password_entry.set_visibility(False)  # Hide password
            self.password_entry.set_placeholder_text("Enter password to unlock")
            self.password_entry.set_width_chars(30)
            self.password_entry.set_halign(Gtk.Align.CENTER)
            self.password_entry.set_margin_start(20)
            self.password_entry.set_margin_end(20)
            self.password_entry.connect("activate", self.on_password_entered)
            self.password_entry.connect("changed", self.on_password_changed)

            # Status label
            self.status_label = Gtk.Label()
            self.status_label.set_margin_top(10)
            self.status_label.set_halign(Gtk.Align.CENTER)

            # Assemble the UI
            self.center_box.append(self.password_entry)
            self.center_box.append(self.status_label)
        else:
            # Non-input screen: show locked message
            self.locked_label = Gtk.Label()
            self.locked_label.set_markup(
                '<span size="large" color="#ebdbb2">Screen Locked</span>'
            )
            self.locked_label.set_halign(Gtk.Align.CENTER)

            # Assemble the UI
            self.center_box.append(self.locked_label)

        self.main_box.append(self.center_box)
        self.main_box.set_valign(Gtk.Align.CENTER)

        self.set_child(self.main_box)

        # Apply styling
        self.apply_styles()

        # Setup layer shell for fullscreen overlay
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        # Set margins to 0 to ensure fullscreen coverage
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, 0)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, 0)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, 0)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, 0)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        GtkLayerShell.auto_exclusive_zone_enable(self)

        # Handle key presses
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(controller)

        # Prevent window closing
        self.connect("close-request", self.on_close_request)

    def apply_styles(self):
        """Apply dark theme styling to the lock screen."""
        # Window styling - make it cover entire screen
        apply_styles(
            self,
            """
            window {
                background: #0e1419;
                color: #ebdbb2;
            }
            """,
        )

        # Main container - full screen background
        apply_styles(
            self.main_box,
            """
            box {
                background: #0e1419;
                padding: 0px;
            }
            """,
        )

        # Center container - lock UI panel
        apply_styles(
            self.center_box,
            """
            box {
                padding: 40px;
            }
            """,
        )

        if self.is_input_enabled:
            # Password entry
            apply_styles(
                self.password_entry,
                """
                entry {
                    background: #0e1419;
                    color: #ebdbb2;
                    border: none;
                    outline: none;
                    box-shadow: none;
                    padding: 12px;
                    font-size: 16px;
                    font-family: Iosevka, monospace;
                }
                entry:focus {
                    border: none;
                    outline: none;
                    box-shadow: none;
                }
                entry:focus-visible {
                    border: none;
                    outline: none;
                    box-shadow: none;
                }
                """,
            )

            # Status label
            apply_styles(
                self.status_label,
                """
                label {
                    font-family: Iosevka, sans-serif;
                    font-size: 14px;
                }
                """,
            )
        else:
            # Locked label
            apply_styles(
                self.locked_label,
                """
                label {
                    font-family: Iosevka, sans-serif;
                    font-size: 24px;
                    font-weight: bold;
                }
                """,
            )

            # Hint label
            apply_styles(
                self.hint_label,
                """
                label {
                    font-family: Iosevka, sans-serif;
                    font-size: 14px;
                }
                """,
            )

    def on_password_changed(self, entry):
        """Reset status label when user starts typing."""
        if self.is_input_enabled:
            self.status_label.set_markup('<span color="#98971a"></span>')

    def on_password_entered(self, entry):
        """Handle password entry when Enter key is pressed."""
        self.check_password()

    def on_unlock_clicked(self, button):
        """Handle unlock button click."""
        self.check_password()

    def check_password(self):
        """Check if the entered password is correct."""
        password = self.password_entry.get_text()
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        if password_hash == self.correct_password_hash:
            # Correct password - unlock
            self.status_label.set_markup('<span color="#98c97c">Unlocking...</span>')
            GLib.timeout_add(500, self.unlock)
        else:
            # Wrong password
            self.attempts += 1
            remaining = self.max_attempts - self.attempts

            if remaining > 0:
                self.status_label.set_markup(
                    f'<span color="#cc241d">Incorrect password! {remaining} attempts remaining</span>'
                )
                self.password_entry.set_text("")
                self.password_entry.grab_focus()

            else:
                # Max attempts reached
                self.status_label.set_markup(
                    '<span color="#fb4934">Maximum attempts reached! Locking...</span>'
                )
                GLib.timeout_add(2000, self.max_attempts_lockdown)

    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events."""
        # Escape to hide password (but not close window) - only for input screens
        if self.is_input_enabled and keyval == Gdk.KEY_Escape:
            self.password_entry.set_text("")
            return True

        # Prevent Alt+Tab, Ctrl+Alt+F1, etc. on all screens
        if (state & Gdk.ModifierType.ALT_MASK and keyval == Gdk.KEY_Tab) or (
            state & Gdk.ModifierType.CONTROL_MASK
            and state & Gdk.ModifierType.ALT_MASK
            and keyval
            in [
                Gdk.KEY_F1,
                Gdk.KEY_F2,
                Gdk.KEY_F3,
                Gdk.KEY_F4,
                Gdk.KEY_F5,
                Gdk.KEY_F6,
                Gdk.KEY_F7,
                Gdk.KEY_F8,
                Gdk.KEY_F9,
                Gdk.KEY_F10,
                Gdk.KEY_F11,
                Gdk.KEY_F12,
            ]
        ):
            return True

        return False

    def on_close_request(self, window):
        """Prevent window from being closed."""
        return True  # Prevent close

    def unlock(self):
        """Unlock the screen."""
        if self.unlock_all_callback and self.is_input_enabled:
            # Input screen: unlock all screens
            self.unlock_all_callback()
        else:
            # Non-input screen or no callback: just unlock this one
            self.hide()
            self.destroy()

    def lock(self):
        """Show the lock screen."""
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("LockScreen.lock() called")

        if self.is_input_enabled:
            self.password_entry.set_text("")
        self.attempts = 0

        # Use assigned monitor or detect it
        monitor = self.monitor
        if not monitor:
            monitor_geo = get_monitor_geometry_for_window(self)
        else:
            monitor_geo = monitor.get_geometry()

        if monitor_geo:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    f"Monitor geometry: {monitor_geo.width}x{monitor_geo.height}"
                )
            # Set window to cover entire monitor
            self.set_default_size(monitor_geo.width, monitor_geo.height)
        else:
            # Fallback size
            self.set_default_size(1920, 1080)

        # Initialize GTK layer shell
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Initializing GTK layer shell...")
        try:
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            keyboard_mode = (
                GtkLayerShell.KeyboardMode.EXCLUSIVE
            )  # Lock keyboard on all screens
            GtkLayerShell.set_keyboard_mode(self, keyboard_mode)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
            # Set margins to 0 to ensure fullscreen coverage
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, 0)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, 0)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, 0)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, 0)
            GtkLayerShell.auto_exclusive_zone_enable(self)
            # Set monitor before presenting if assigned
            if monitor:
                try:
                    GtkLayerShell.set_monitor(self, monitor)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("Monitor set for layer shell before present")
                except Exception as e:
                    if logger.isEnabledFor(logging.ERROR):
                        logger.error(f"Failed to set monitor before present: {e}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("GTK layer shell initialized successfully")
        except Exception as e:
            if logger.isEnabledFor(logging.ERROR):
                logger.error(f"Failed to initialize GTK layer shell: {e}")

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Presenting lock screen window...")
        try:
            self.present()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Window presented successfully")
        except Exception as e:
            if logger.isEnabledFor(logging.ERROR):
                logger.error(f"Failed to present window: {e}")

        if self.is_input_enabled:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Grabbing focus on password entry...")
            self.password_entry.grab_focus()


def create_lock_screen(
    password="admin",
    application=None,
    monitor=None,
    is_input_enabled=True,
    unlock_all_callback=None,
):
    """Create and return a lock screen instance."""
    return LockScreen(
        password=password,
        application=application,
        monitor=monitor,
        is_input_enabled=is_input_enabled,
        unlock_all_callback=unlock_all_callback,
    )
