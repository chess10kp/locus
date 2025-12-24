# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import logging
from typing import Dict, Any, Optional

from gi.repository import Gtk, Gdk, GdkPixbuf
from utils import apply_styles

logger = logging.getLogger("LauncherUI")


class LauncherUI:
    """Manages UI factory setup and size modes for the Launcher."""

    def __init__(self, launcher):
        self.launcher = launcher

    def setup_list_view_factory(self):
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
                    "clicked", self.launcher._on_list_item_clicked, search_result
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

        self.launcher.list_view.set_factory(factory)

    def setup_wallpaper_factory(self):
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
                "clicked", self.launcher._on_list_item_clicked, search_result
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

    def setup_grid_factory(self, grid_config):
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
                "clicked", self.launcher._on_list_item_clicked, search_result
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
        factory = self.setup_wallpaper_factory()
        self.launcher.list_view.set_factory(factory)

        # Switch to list view if needed
        try:
            current_child = self.launcher.scrolled.get_child()
            if self.launcher.grid_view and current_child == self.launcher.grid_view:
                # Unparent the current grid view
                self.launcher.grid_view.unparent()
                self.launcher.scrolled.set_child(self.launcher.list_view)
                self.launcher.current_view = self.launcher.list_view
        except Exception:
            # If there's an error, ensure we're using list view
            if hasattr(self.launcher, "list_view"):
                self.launcher.scrolled.set_child(self.launcher.list_view)
                self.launcher.current_view = self.launcher.list_view

    def set_grid_factory(self, grid_config):
        """Switch to grid factory for grid view with configurable layout."""
        # Create GridView if not exists
        if self.launcher.grid_view is None:
            self.launcher.grid_view = Gtk.GridView.new(self.launcher.selection_model)
            self.launcher.grid_view.set_vexpand(True)
            self.launcher.grid_view.set_max_columns(grid_config.get("columns", 4))

        # Set factory for grid
        factory = self.setup_grid_factory(grid_config)
        self.launcher.grid_view.set_factory(factory)

        # Switch to grid view
        try:
            current_child = self.launcher.scrolled.get_child()
            if current_child == self.launcher.list_view:
                self.launcher.list_view.unparent()
                self.launcher.scrolled.set_child(self.launcher.grid_view)
                self.launcher.current_view = self.launcher.grid_view
            elif current_child != self.launcher.grid_view:
                self.launcher.scrolled.set_child(self.launcher.grid_view)
                self.launcher.current_view = self.launcher.grid_view
        except Exception:
            # Fallback - ensure grid view is set
            self.launcher.scrolled.set_child(self.launcher.grid_view)
            self.launcher.current_view = self.launcher.grid_view

    def set_default_factory(self):
        """Switch back to default factory for text-based results."""
        # Recreate the default factory
        self.setup_list_view_factory()

        # Switch back to list view if needed
        try:
            current_child = self.launcher.scrolled.get_child()
            if self.launcher.grid_view and current_child == self.launcher.grid_view:
                # Unparent the current grid view
                self.launcher.grid_view.unparent()
                self.launcher.scrolled.set_child(self.launcher.list_view)
                self.launcher.current_view = self.launcher.list_view

        except Exception:
            # Fallback - ensure list view is set
            if hasattr(self.launcher, "grid_view") and self.launcher.grid_view:
                self.launcher.scrolled.set_child(self.launcher.list_view)
                self.launcher.current_view = self.launcher.list_view

    def set_wallpaper_mode_size(self):
        """Increase launcher size for wallpaper mode to accommodate larger thumbnails."""
        from .config import LAUNCHER_CONFIG

        window_config = LAUNCHER_CONFIG["window"]
        self.launcher.set_default_size(
            window_config["wallpaper_width"], window_config["wallpaper_height"]
        )

    def reset_launcher_size(self):
        """Reset launcher to default size for non-wallpaper modes."""
        from .config import LAUNCHER_CONFIG

        window_config = LAUNCHER_CONFIG["window"]
        self.launcher.set_default_size(
            window_config["default_width"], window_config["default_height"]
        )

    def apply_size_mode(self, size_mode, custom_size):
        """Apply the appropriate size mode for the launcher."""
        if size_mode.name == "WALLPAPER":
            self.set_wallpaper_mode_size()
            self.set_wallpaper_factory()
        elif size_mode.name == "GRID":
            # Grid mode - get grid config from launcher
            launcher = None  # Need to get the current launcher instance
            # Find the current launcher that triggered grid mode
            if (
                hasattr(self.launcher, "_current_grid_launcher")
                and self.launcher._current_grid_launcher
            ):
                launcher = self.launcher._current_grid_launcher
                grid_config = launcher.get_grid_config()
                if grid_config and custom_size:
                    width, height = custom_size
                    self.launcher.set_default_size(width, height)
                elif grid_config:
                    # Calculate size based on grid config
                    columns = grid_config.get("columns", 3)
                    item_width = grid_config.get("item_width", 200)
                    item_height = grid_config.get("item_height", 200)
                    spacing = grid_config.get("spacing", 10)
                    total_width = (columns * item_width) + ((columns + 1) * spacing)
                    total_height = (4 * item_height) + (5 * spacing)  # Max 4 rows
                    self.launcher.set_default_size(total_width, total_height)
                # Set grid factory with config
                self.set_grid_factory(grid_config)
            else:
                # Fallback to default if no launcher available
                self.reset_launcher_size()
                self.set_default_factory()
        elif size_mode.name == "CUSTOM" and custom_size:
            width, height = custom_size
            self.launcher.set_default_size(width, height)
            # Center the launcher horizontally for custom sizes
            from gi.repository import GtkLayerShell

            screen = Gdk.Display.get_default().get_monitor_at_surface(
                self.launcher.get_surface()
            )
            if screen:
                monitor_geometry = screen.get_geometry()
                center_x = monitor_geometry.width // 2
                GtkLayerShell.set_anchor(self.launcher, GtkLayerShell.Edge.LEFT, True)
                GtkLayerShell.set_anchor(self.launcher, GtkLayerShell.Edge.RIGHT, True)
                GtkLayerShell.set_margin(
                    self.launcher, GtkLayerShell.Edge.LEFT, center_x - width // 2
                )
            self.set_default_factory()
        else:
            self.reset_launcher_size()
            self.set_default_factory()
