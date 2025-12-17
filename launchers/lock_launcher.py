# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from gi.repository import GLib, Gdk, Gtk, Gtk4LayerShell as GtkLayerShell  # pyright: ignore
from typing_extensions import final
import hashlib
import getpass
import subprocess
import os
from utils import apply_styles, VBox, HBox


@final
class LockScreen(Gtk.ApplicationWindow):
    def __init__(self, password="password123", **kwargs):
        super().__init__(
            **kwargs,
            title="lock-screen",
            show_menubar=False,
            child=None,
            fullscreened=True,
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
        self.main_box.set_valign(Gtk.Align.CENTER)
        self.main_box.set_halign(Gtk.Align.CENTER)

        # Title
        self.title_label = Gtk.Label()
        self.title_label.set_markup('<span size="xx-large" weight="bold">Screen Locked</span>')
        self.title_label.set_margin_bottom(20)

        # Password entry
        self.password_entry = Gtk.Entry()
        self.password_entry.set_visibility(False)  # Hide password
        self.password_entry.set_placeholder_text("Enter password to unlock")
        self.password_entry.set_width_chars(30)
        self.password_entry.connect("activate", self.on_password_entered)
        self.password_entry.connect("changed", self.on_password_changed)

        # Unlock button
        self.unlock_button = Gtk.Button(label="Unlock")
        self.unlock_button.connect("clicked", self.on_unlock_clicked)
        self.unlock_button.set_margin_top(10)

        # Status label
        self.status_label = Gtk.Label()
        self.status_label.set_markup('<span color="#cc241d">Please enter your password</span>')
        self.status_label.set_margin_top(10)

        # Assemble the UI
        self.main_box.append(self.title_label)
        self.main_box.append(self.password_entry)
        self.main_box.append(self.unlock_button)
        self.main_box.append(self.status_label)

        self.set_child(self.main_box)

        # Apply styling
        self.apply_styles()

        # Setup layer shell for fullscreen overlay
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
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
        # Window styling
        apply_styles(
            self,
            """
            window {
                background: #1d2021;
                color: #ebdbb2;
            }
            """,
        )

        # Main container
        apply_styles(
            self.main_box,
            """
            box {
                background: #282828;
                border-radius: 15px;
                padding: 40px;
                border: 2px solid #3c3836;
            }
            """,
        )

        # Title label
        apply_styles(
            self.title_label,
            """
            label {
                color: #ebdbb2;
                font-family: Iosevka, sans-serif;
                font-weight: bold;
            }
            """,
        )

        # Password entry
        apply_styles(
            self.password_entry,
            """
            entry {
                background: #1d2021;
                color: #ebdbb2;
                border: 2px solid #3c3836;
                border-radius: 8px;
                padding: 12px;
                font-size: 16px;
                font-family: Iosevka, monospace;
            }
            entry:focus {
                border-color: #83a598;
                box-shadow: 0 0 5px #83a598;
            }
            """,
        )

        # Unlock button
        apply_styles(
            self.unlock_button,
            """
            button {
                background: #458588;
                color: #ebdbb2;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 16px;
                font-family: Iosevka, sans-serif;
                font-weight: bold;
            }
            button:hover {
                background: #50868a;
            }
            button:active {
                background: #3a7477;
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
        self.status_label.set_markup('<span color="#98971a">Enter password to unlock</span>')

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
                self.status_label.set_markup('<span color="#fb4934">Maximum attempts reached! Locking...</span>')
                GLib.timeout_add(2000, self.max_attempts_lockdown)

    def shake_window(self):
        """Shake the window for incorrect password feedback."""
        original_position = self.get_position()
        shake_distance = 10
        shake_duration = 50  # milliseconds

        def shake_step(step):
            if step < 6:  # 6 shakes (left, right, left, right, left, center)
                if step % 2 == 0:
                    offset = shake_distance
                else:
                    offset = -shake_distance
                self.move(original_position[0] + offset, original_position[1])
                GLib.timeout_add(shake_duration, lambda: shake_step(step + 1))
            else:
                self.move(original_position[0], original_position[1])

        shake_step(0)

    def max_attempts_lockdown(self):
        """Handle max attempts lockdown."""
        # You could implement additional security measures here
        # For now, just reset attempts but show a warning
        self.attempts = 0
        self.status_label.set_markup('<span color="#fb4934">Session temporarily locked. Please wait...</span>')
        GLib.timeout_add(5000, self.reset_after_lockdown)

    def reset_after_lockdown(self):
        """Reset after temporary lockdown."""
        self.password_entry.set_text("")
        self.status_label.set_markup('<span color="#cc241d">Please enter your password</span>')
        self.password_entry.grab_focus()

    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events."""
        # Escape to hide password (but not close window)
        if keyval == Gdk.KEY_Escape:
            self.password_entry.set_text("")
            return True

        # Prevent Alt+Tab, Ctrl+Alt+F1, etc.
        if (state & Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_Tab) or \
           (state & Gdk.ModifierType.CONTROL_MASK and state & Gdk.ModifierType.MOD1_MASK and
            keyval in [Gdk.KEY_F1, Gdk.KEY_F2, Gdk.KEY_F3, Gdk.KEY_F4, Gdk.KEY_F5, Gdk.KEY_F6, Gdk.KEY_F7, Gdk.KEY_F8, Gdk.KEY_F9, Gdk.KEY_F10, Gdk.KEY_F11, Gdk.KEY_F12]):
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
        self.password_entry.set_text("")
        self.attempts = 0
        self.status_label.set_markup('<span color="#cc241d">Please enter your password</span>')
        self.present()
        self.password_entry.grab_focus()


def create_lock_screen(password="password123", application=None):
    """Create and return a lock screen instance."""
    return LockScreen(password=password, application=application)