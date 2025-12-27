# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from typing import Tuple, Optional

from gi.repository import Gtk, GLib

from core.statusbar_interface import (
    StatusbarModuleInterface,
    StatusbarUpdateMode,
    StatusbarSizeMode,
)


class CustomMessageModule(StatusbarModuleInterface):
    """Statusbar module for displaying custom IPC messages and progress bars."""

    def __init__(self):
        self.current_message = ""
        self.progress_visible = False
        self.icon = Gtk.Image()
        self.icon.set_pixel_size(14)

    @property
    def name(self) -> str:
        return "custom_message"

    @property
    def update_mode(self) -> StatusbarUpdateMode:
        return StatusbarUpdateMode.ON_DEMAND

    def create_widget(self) -> Gtk.Widget:
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(200)
        self.stack.set_halign(Gtk.Align.CENTER)

        self.label = Gtk.Label()
        self.label.set_name("custom-message-label")

        # Create progress box with icon and progress bar
        self.progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self.progress_box.set_name("custom-progress-box")

        self.icon.set_name("custom-progress-icon")

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_name("custom-progress-bar")
        self.progress_bar.set_size_request(
            100, 20
        )  # Reduced width since icon takes space
        self.progress_bar.set_show_text(False)  # Disable text, use icon instead

        self.progress_box.append(self.icon)
        self.progress_box.append(self.progress_bar)

        # Center the icon and progress bar vertically
        self.icon.set_valign(Gtk.Align.CENTER)
        self.progress_bar.set_valign(Gtk.Align.CENTER)

        self.stack.add_named(self.label, "label")
        self.stack.add_named(self.progress_box, "progress")

        self.stack.set_visible_child_name("label")

        return self.stack

    def update(self, widget: Gtk.Widget) -> None:
        if self.progress_visible:
            self.stack.set_visible_child_name("progress")
            self.stack.set_visible(True)
        else:
            self.stack.set_visible_child_name("label")
            self.label.set_text(self.current_message)
            self.stack.set_visible(bool(self.current_message))
        widget.queue_draw()

    def get_size_mode(self) -> Tuple[StatusbarSizeMode, Optional[Tuple[int, int]]]:
        return StatusbarSizeMode.DEFAULT, None

    def handles_ipc_messages(self) -> bool:
        return True

    def handle_ipc_message(self, message: str, widget: Gtk.Widget) -> bool:
        """Handle IPC message for custom status display."""
        if message.startswith("status:"):
            # Extract the actual status message
            status_text = message[7:]  # Remove "status:" prefix
            self.current_message = status_text
            self.progress_visible = False
            self.update(widget)
            return True
        elif message.startswith("progress:"):
            # Handle progress bar: progress:type:value[:mute]
            parts = message[9:].split(":")  # Remove "progress:" prefix
            if len(parts) >= 2:
                progress_type = parts[0]
                try:
                    value = int(parts[1])
                    fraction = value / 100.0

                    self.progress_bar.set_fraction(fraction)
                    if progress_type == "volume":
                        if len(parts) > 2 and parts[2] == "mute":
                            self.icon.set_from_icon_name("audio-volume-muted-symbolic")
                        else:
                            self.icon.set_from_icon_name("audio-volume-high-symbolic")
                    elif progress_type == "brightness":
                        self.icon.set_from_icon_name("display-brightness-symbolic")
                    else:
                        # For other types, use a generic icon or keep text
                        self.icon.set_from_icon_name("dialog-information-symbolic")
                        self.progress_bar.set_show_text(True)
                        self.progress_bar.set_text(progress_type.title())

                    self.progress_visible = True
                    self.update(widget)

                    # Auto-hide after 3 seconds
                    GLib.timeout_add_seconds(3, self._hide_progress, widget)

                    return True
                except ValueError:
                    pass
        return False

    def _hide_progress(self, widget: Gtk.Widget) -> bool:
        """Hide the progress bar and show label if there's a message."""
        self.progress_visible = False
        self.update(widget)
        return False

    def get_styles(self) -> Optional[str]:
        return """
        #custom-message-label {
            padding: 0 8px;
            font-size: 10px;
            font-weight: 500;
            color: #f1fa8c;
            background: #0e1419;
            border-radius: 4px;
        }
        #custom-progress-box {
            padding: 0 4px;
            background: #0e1419;
            border-radius: 4px;
        }
        #custom-progress-icon {
            color: #f1fa8c;
            background: #0e1419;
        }
        #custom-progress-bar {
            min-width: 100px;
            padding: 0 4px;
            background: #0e1419;
            border-radius: 4px;
        }
        #custom-progress-bar trough {
            background-color: #0e1419;
            border-radius: 4px;
        }
        #custom-progress-bar progress {
            background-color: #f1fa8c;
            border-radius: 4px;
        }
        """
