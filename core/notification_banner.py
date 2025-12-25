# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from typing import Optional, Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("Pango", "1.0")

from gi.repository import (
    Gtk,
    GLib,
    Gdk,
    Gtk4LayerShell as GtkLayerShell,
    Pango,
)

LayerShell = GtkLayerShell
Layer = GtkLayerShell.Layer
Edge = GtkLayerShell.Edge
KeyboardMode = GtkLayerShell.KeyboardMode

from core.notification_store import Notification
from utils.icon_manager import IconManager


class NotificationBanner(Gtk.ApplicationWindow):
    """Floating notification banner window."""

    URGENCY_COLORS = {
        "low": "#89b4fa",
        "normal": "#cba6f7",
        "critical": "#f38ba8",
    }

    URGENCY_TIMEOUTS = {
        "low": 3000,
        "normal": 5000,
        "critical": -1,
    }

    def __init__(
        self,
        notification: Notification,
        on_close: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.notification = notification
        self.on_close = on_close
        self.dismiss_timeout_id = None
        self.icon_manager = IconManager()

        self._setup_window()
        self._build_ui()
        self._setup_layer_shell()
        self._start_dismiss_timer()
        self._animate_in()

    def _setup_window(self) -> None:
        """Set up window properties."""
        self.set_title("Notification")
        self.set_resizable(False)
        self.set_decorated(False)
        self.set_default_size(400, 100)

    def _setup_layer_shell(self) -> None:
        """Set up layer shell for Wayland positioning."""
        LayerShell.init_for_window(self)
        LayerShell.set_layer(self, Layer.OVERLAY)
        LayerShell.set_keyboard_mode(self, KeyboardMode.NONE)
        LayerShell.set_anchor(self, Edge.TOP, True)
        LayerShell.set_anchor(self, Edge.RIGHT, True)
        LayerShell.set_margin(self, Edge.TOP, 40)
        LayerShell.set_margin(self, Edge.RIGHT, 10)

    def _get_urgency(self) -> str:
        """Get urgency level from notification hints."""
        urgency = self.notification.hints.get("urgency", 1)
        if urgency == 0:
            return "low"
        elif urgency == 2:
            return "critical"
        else:
            return "normal"

    def _get_timeout(self) -> int:
        """Get timeout for this notification."""
        if self.notification.expire_timeout == -1:
            return -1
        return self.notification.expire_timeout

    def _build_ui(self) -> None:
        """Build the banner UI."""
        urgency = self._get_urgency()
        border_color = self.URGENCY_COLORS.get(urgency, "#cba6f7")

        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)

        icon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        icon_widget = Gtk.Image()
        icon_widget.set_pixel_size(48)

        self._load_icon(icon_widget)

        icon_box.append(icon_widget)
        main_box.append(icon_box)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content_box.set_hexpand(True)

        title_label = Gtk.Label(label=self.notification.summary)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_wrap(True)
        title_label.set_max_width_chars(40)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)

        title_style = """
            label {
                font-weight: bold;
                font-size: 13px;
                color: #f8f8f2;
            }
        """
        self._apply_style(title_label, title_style)

        body_label = Gtk.Label(label=self.notification.body)
        body_label.set_halign(Gtk.Align.START)
        body_label.set_wrap(True)
        body_label.set_max_width_chars(40)
        body_label.set_lines(3)
        body_label.set_ellipsize(Pango.EllipsizeMode.END)

        body_style = """
            label {
                font-size: 12px;
                color: #b8bb26;
            }
        """
        self._apply_style(body_label, body_style)

        content_box.append(title_label)
        if self.notification.body:
            content_box.append(body_label)

        app_label = Gtk.Label(label=self.notification.app_name)
        app_label.set_halign(Gtk.Align.START)
        app_label.set_sensitive(False)

        app_style = """
            label {
                font-size: 10px;
                color: #6272a4;
            }
        """
        self._apply_style(app_label, app_style)
        content_box.append(app_label)

        main_box.append(content_box)

        main_box_style = f"""
            box {{
                background-color: rgba(28, 27, 34, 0.95);
                border-left: 3px solid {border_color};
                border-radius: 4px;
            }}
        """
        self._apply_style(main_box, main_box_style)

        close_button = Gtk.Button(label="×")
        close_button.set_has_frame(False)
        close_style = """
            button {
                padding: 4px 8px;
                font-size: 18px;
                color: #8be9fd;
                background: none;
                border: none;
            }
            button:hover {
                color: #ff5555;
                background: rgba(255, 85, 85, 0.2);
            }
        """
        self._apply_style(close_button, close_style)
        close_button.connect("clicked", self._on_close_clicked)

        main_box.append(close_button)

        self.set_child(main_box)

        click_handler = Gtk.GestureClick()
        click_handler.connect("pressed", self._on_banner_clicked)
        main_box.add_controller(click_handler)

        hover_controller = Gtk.EventControllerMotion()
        hover_controller.connect("enter", self._on_hover_enter)
        main_box.add_controller(hover_controller)

    def _load_icon(self, icon_widget: Gtk.Image) -> None:
        """Load icon for notification."""
        icon_name = self.notification.app_icon
        if not icon_name:
            icon_name = "dialog-information"

        def set_icon(pixbuf):
            if pixbuf:
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                icon_widget.set_from_paintable(texture)

        self.icon_manager.get_icon_async(icon_name=icon_name, callback=set_icon)

    def _apply_style(self, widget: Gtk.Widget, css: str) -> None:
        """Apply CSS styles to a widget."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode())
        style_context = widget.get_style_context()
        style_context.add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _start_dismiss_timer(self) -> None:
        """Start auto-dismiss timer."""
        timeout = self._get_timeout()

        if timeout > 0:
            self.dismiss_timeout_id = GLib.timeout_add(
                timeout, self._on_dismiss_timeout
            )

    def _stop_dismiss_timer(self) -> None:
        """Stop auto-dismiss timer."""
        if self.dismiss_timeout_id:
            GLib.source_remove(self.dismiss_timeout_id)
            self.dismiss_timeout_id = None

    def _on_dismiss_timeout(self) -> bool:
        """Handle dismiss timeout."""
        self.dismiss()
        return False

    def _animate_in(self) -> None:
        """Simple slide-in animation."""
        self.set_opacity(0)

        def fade_in():
            current = self.get_opacity()
            if current < 1.0:
                self.set_opacity(min(current + 0.1, 1.0))
                return True
            return False

        GLib.timeout_add(20, fade_in)

    def _animate_out(self, callback: Optional[Callable] = None) -> None:
        """Simple slide-out animation."""

        def fade_out():
            current = self.get_opacity()
            if current > 0:
                self.set_opacity(max(current - 0.1, 0))
                return True
            if callback:
                callback()
            return False

        GLib.timeout_add(20, fade_out)

    def _on_close_clicked(self, button) -> None:
        """Handle close button click."""
        self.dismiss()

    def _on_banner_clicked(self, gesture, n_press, x, y) -> None:
        """Handle banner click."""
        self.dismiss()

    def _on_hover_enter(self, controller, x, y) -> None:
        """Handle hover enter - pause auto-dismiss."""
        urgency = self._get_urgency()
        if urgency != "critical":
            self._stop_dismiss_timer()

    def dismiss(self) -> None:
        """Dismiss the banner."""
        self._stop_dismiss_timer()

        def destroy_banner():
            if self.on_close:
                self.on_close(self.notification.id)
            self.destroy()

        self._animate_out(destroy_banner)

    def update_position(self, x: int, y: int) -> None:
        """Update banner position."""
        LayerShell.set_margin(self, Edge.TOP, y)
        LayerShell.set_margin(self, Edge.RIGHT, x)
