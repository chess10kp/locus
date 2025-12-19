# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from typing import Tuple, Optional, List, Callable

from gi.repository import Gtk
from utils.wm import detect_wm
from utils.utils import HBox
from core.statusbar_interface import (
    StatusbarModuleInterface,
    StatusbarUpdateMode,
    StatusbarSizeMode,
)


class WorkspacesModule(StatusbarModuleInterface):
    """Statusbar module for displaying workspace indicators."""

    def __init__(self, show_labels: bool = True, highlight_focused: bool = True):
        self.show_labels = show_labels
        self.highlight_focused = highlight_focused
        self.wm_client = detect_wm()
        self.workspace_widgets = {}
        self.box_container = None

    @property
    def name(self) -> str:
        return "workspaces"

    @property
    def update_mode(self) -> StatusbarUpdateMode:
        return StatusbarUpdateMode.EVENT_DRIVEN

    def create_widget(self) -> Gtk.Widget:
        # Create a horizontal box container for workspace buttons
        self.box_container = HBox(spacing=30)
        self.box_container.set_name("workspaces-container")

        # Initial update
        self.update(self.box_container)
        return self.box_container

    def update(self, widget: Gtk.Widget) -> None:
        """Update workspace display."""
        try:
            workspaces = self.wm_client.get_workspaces()
            if not workspaces:
                return

            # Check if any workspace is focused
            any_focused = any(ws.focused for ws in workspaces)

            # Clear all existing children from the container
            child = widget.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                widget.remove(child)
                child = next_child
            self.workspace_widgets.clear()

            # Create workspace widgets
            for i, workspace in enumerate(workspaces):
                # Create workspace button
                if self.show_labels:
                    label_text = workspace.name
                else:
                    label_text = ""

                ws_button = Gtk.Button(label=label_text)
                ws_button.set_has_frame(False)
                ws_button.set_name(f"workspace-{workspace.num}")

                # Apply styles
                styles = self._get_workspace_styles(workspace, any_focused)
                self._apply_styles(ws_button, styles)

                # Add widget to container
                widget.append(ws_button)
                self.workspace_widgets[workspace.num] = ws_button

            # Container is shown by default in GTK4

        except Exception as e:
            print(f"Error updating workspaces: {e}")

    def setup_event_listeners(self, status_bar) -> List[Callable]:
        """Set up event listeners for workspace changes."""
        listeners = []

        if self.wm_client:
            # Create a callback that updates this module
            def workspace_callback():
                if self.box_container:
                    # Schedule update in main thread
                    from gi.repository import GLib

                    GLib.idle_add(self.update, self.box_container)

            try:
                self.wm_client.start_event_listener(workspace_callback)
                listeners.append(self.wm_client)
            except Exception as e:
                print(f"Error setting up workspace event listener: {e}")

        return listeners

    def _get_workspace_styles(self, workspace, any_focused: bool = False) -> str:
        """Get CSS styles for a workspace widget."""
        base_styles = """
            padding: 4px 6px;
            font-size: 12px;
            font-weight: 500;
            margin: 0 2px;
            border-radius: 3px;
            transition: all 0.2s ease;
        """

        # Highlight workspace 1 as default if no workspace is focused
        is_default_highlight = workspace.num == 1 and not any_focused

        if (workspace.focused or is_default_highlight) and self.highlight_focused:
            return (
                base_styles
                + """
                color: #f8f8f2;
                background: #50fa7b;
            """
            )
        elif workspace.urgent:
            return (
                base_styles
                + """
                color: #ff5555;
                background: rgba(255, 85, 85, 0.2);
            """
            )
        elif workspace.visible:
            return (
                base_styles
                + """
                color: #f8f8f2;
                background: rgba(248, 248, 242, 0.1);
            """
            )
        else:
            return (
                base_styles
                + """
                color: #6272a4;
                background: transparent;
            """
            )

    def _apply_styles(self, widget: Gtk.Widget, css: str):
        """Apply CSS styles to a widget."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode())
        style_context = widget.get_style_context()
        style_context.add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def get_size_mode(self) -> Tuple[StatusbarSizeMode, Optional[Tuple[int, int]]]:
        return StatusbarSizeMode.DEFAULT, None

    def get_styles(self) -> Optional[str]:
        return """
        #workspaces-container {
            padding: 0 8px;
        }
        """
