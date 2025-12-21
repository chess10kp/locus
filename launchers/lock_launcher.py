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


@final
class LockScreen(Gtk.ApplicationWindow):
    def __init__(self, password="admin", **kwargs):
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

        # Create main container
        self.main_box = VBox(spacing=20)
        self.main_box.set_valign(Gtk.Align.FILL)
        self.main_box.set_halign(Gtk.Align.FILL)

        # Create center container for lock UI
        self.center_box = VBox(spacing=20)
        self.center_box.set_valign(Gtk.Align.CENTER)
        self.center_box.set_halign(Gtk.Align.CENTER)

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
        self.status_label.set_markup(
            '<span color="#cc241d">Please enter your password</span>'
        )
        self.status_label.set_margin_top(10)
        self.status_label.set_halign(Gtk.Align.CENTER)

        # Assemble the UI
        self.center_box.append(self.password_entry)
        self.center_box.append(self.status_label)
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

        # Password entry
        apply_styles(
            self.password_entry,
            """
            entry {
                background: #0e1419;
                color: #ebdbb2;
                border: 0px solid #3c3836;
                padding: 12px;
                font-size: 16px;
                font-family: Iosevka, monospace;
            }
            entry:focus {
                border: 0px ;
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

    def on_password_changed(self, entry):
        """Reset status label when user starts typing."""
        self.status_label.set_markup(
            '<span color="#98971a"></span>'
        )

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

                # Shake the window for visual feedback
                self.shake_window()
            else:
                # Max attempts reached
                self.status_label.set_markup(
                    '<span color="#fb4934">Maximum attempts reached! Locking...</span>'
                )
                GLib.timeout_add(2000, self.max_attempts_lockdown)

    def shake_window(self):
        """Shake the lock UI for incorrect password feedback."""
        shake_distance = 15
        shake_duration = 80  # milliseconds

        # Store original margin
        original_margin = self.center_box.get_margin_top()

        def shake_step(step):
            if step < 6:  # 6 shakes (left, right, left, right, left, center)
                if step % 2 == 0:
                    self.center_box.set_margin_top(original_margin + shake_distance)
                else:
                    self.center_box.set_margin_top(original_margin - shake_distance)

                if step < 5:
                    GLib.timeout_add(shake_duration, lambda: shake_step(step + 1))
                else:
                    # Reset margin
                    self.center_box.set_margin_top(original_margin)

        shake_step(0)

    def max_attempts_lockdown(self):
        """Handle max attempts lockdown."""
        # You could implement additional security measures here
        # For now, just reset attempts but show a warning
        self.attempts = 0
        self.status_label.set_markup(
            '<span color="#fb4934">Session temporarily locked. Please wait...</span>'
        )
        GLib.timeout_add(5000, self.reset_after_lockdown)

    def reset_after_lockdown(self):
        """Reset after temporary lockdown."""
        self.password_entry.set_text("")
        self.status_label.set_markup(
            '<span color="#cc241d">Please enter your password</span>'
        )
        self.password_entry.grab_focus()

    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events."""
        # Escape to hide password (but not close window)
        if keyval == Gdk.KEY_Escape:
            self.password_entry.set_text("")
            return True

        # Prevent Alt+Tab, Ctrl+Alt+F1, etc.
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
        self.hide()
        self.destroy()

    def lock(self):
        """Show the lock screen."""
        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] LockScreen.lock() called\n")

        self.password_entry.set_text("")
        self.attempts = 0
        self.status_label.set_markup(
            '<span color="#cc241d">Please enter your password</span>'
        )

        # Ensure the window covers the entire screen
        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] Getting monitor geometry...\n")
        monitor_geo = get_monitor_geometry_for_window(self)
        if monitor_geo:
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] Monitor geometry: {monitor_geo.width}x{monitor_geo.height}\n")
            # Set window to cover entire monitor
            self.set_default_size(monitor_geo.width, monitor_geo.height)
            # Maximize the window
            self.maximize()
        else:
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] No monitor geometry, just maximizing\n")
            # Fallback - just maximize
            self.maximize()

        # Initialize GTK layer shell
        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] Initializing GTK layer shell...\n")
        try:
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] GTK layer shell initialized successfully\n")
        except Exception as e:
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[ERROR] Failed to initialize GTK layer shell: {e}\n")

        # Try to set the monitor for GTK layer shell
        try:
            display = Gdk.Display.get_default()
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] Display: {display}\n")
            if display:
                monitor = (
                    display.get_monitor_at_surface(self.get_surface())
                    if self.get_surface()
                    else None
                )
                with open("/tmp/locus_debug.log", "a") as f:
                    f.write(f"[DEBUG] Monitor: {monitor}\n")
                if monitor:
                    GtkLayerShell.set_monitor(self, monitor)
                    with open("/tmp/locus_debug.log", "a") as f:
                        f.write(f"[DEBUG] Monitor set for layer shell\n")
        except Exception as e:
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[ERROR] Failed to set monitor: {e}\n")

        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] Presenting lock screen window...\n")
        try:
            self.present()
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[DEBUG] Window presented successfully\n")
        except Exception as e:
            with open("/tmp/locus_debug.log", "a") as f:
                f.write(f"[ERROR] Failed to present window: {e}\n")

        with open("/tmp/locus_debug.log", "a") as f:
            f.write(f"[DEBUG] Grabbing focus on password entry...\n")
        self.password_entry.grab_focus()


def create_lock_screen(password="admin", application=None):
    """Create and return a lock screen instance."""
    return LockScreen(password=password, application=application)
