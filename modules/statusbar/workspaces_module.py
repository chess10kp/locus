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
from core.statusbar_interface import (
    StatusbarModuleInterface,
    StatusbarUpdateMode,
    StatusbarSizeMode,
)


class WorkspacesModule(StatusbarModuleInterface):
    """Statusbar module for displaying workspace indicators."""

    def __init__(self, show_numbers: bool = True, highlight_focused: bool = True):
        self.show_numbers = show_numbers
        self.highlight_focused = highlight_focused
        self.wm_client = detect_wm()
        self.workspace_widgets = {}
        self.highlight = None
        self.fixed_container = None

    @property
    def name(self) -> str:
        return "workspaces"

    @property
    def update_mode(self) -> StatusbarUpdateMode:
        return StatusbarUpdateMode.EVENT_DRIVEN

    def create_widget(self) -> Gtk.Widget:
        # Create a fixed container for precise positioning
        self.fixed_container = Gtk.Fixed()
        self.fixed_container.set_name("workspaces-container")

        # Initial update
        self.update(self.fixed_container)
        return self.fixed_container

    def update(self, widget: Gtk.Widget) -> None:
        """Update workspace display."""
        try:
            workspaces = self.wm_client.get_workspaces()
            if not workspaces:
                return

            # Clear existing widgets
            for ws_widget in self.workspace_widgets.values():
                if ws_widget.get_parent():
                    widget.remove(ws_widget)
            self.workspace_widgets.clear()

            # Clear existing highlight
            if self.highlight:
                if self.highlight.get_parent():
                    widget.remove(self.highlight)
                self.highlight = None

            # Create workspace widgets
            x_offset = 0
            for i, workspace in enumerate(workspaces):
                # Create workspace label
                if self.show_numbers:
                    label_text = str(i + 1)
                else:
                    label_text = ""

                ws_label = Gtk.Label(label=label_text)
                ws_label.set_name(f"workspace-{workspace.num}")

                # Apply styles
                styles = self._get_workspace_styles(workspace)
                self._apply_styles(ws_label, styles)

                # Position the widget
                widget.put(ws_label, x_offset, 0)
                self.workspace_widgets[workspace.num] = ws_label

                # Update x_offset for next workspace
                x_offset += 30  # 30px spacing between workspaces

                # Add highlight if this workspace is focused
                if self.highlight_focused and workspace.focused:
                    self.highlight = Gtk.Label()
                    self.highlight.set_name("workspace-highlight")
                    self._apply_styles(self.highlight, self._get_highlight_styles())
                    widget.put(self.highlight, x_offset - 25, 0)

            # Show the container
            widget.show_all()

        except Exception as e:
            print(f"Error updating workspaces: {e}")

    def setup_event_listeners(self, status_bar) -> List[Callable]:
        """Set up event listeners for workspace changes."""
        listeners = []

        if self.wm_client:
            # Create a callback that updates this module
            def workspace_callback():
                if self.fixed_container:
                    # Schedule update in main thread
                    from gi.repository import GLib

                    GLib.idle_add(self.update, self.fixed_container)

            try:
                self.wm_client.start_event_listener(workspace_callback)
                listeners.append(self.wm_client)
            except Exception as e:
                print(f"Error setting up workspace event listener: {e}")

        return listeners

    def _get_workspace_styles(self, workspace) -> str:
        """Get CSS styles for a workspace widget."""
        base_styles = """
            padding: 4px 6px;
            font-size: 12px;
            font-weight: 500;
            margin: 0 2px;
            border-radius: 3px;
            transition: all 0.2s ease;
        """

        if workspace.focused:
            return (
                base_styles
                + """
                color: #282a36;
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

    def _get_highlight_styles(self) -> str:
        """Get CSS styles for the workspace highlight indicator."""
        return """
            background: #50fa7b;
            width: 3px;
            height: 16px;
            border-radius: 1.5px;
            margin: 2px 0;
        """

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
