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
from utils.utils import HBox, apply_styles
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
        self.fixed = None

    @property
    def name(self) -> str:
        return "workspaces"

    @property
    def update_mode(self) -> StatusbarUpdateMode:
        return StatusbarUpdateMode.EVENT_DRIVEN

    def create_widget(self) -> Gtk.Widget:
        from utils.utils import apply_styles

        self.fixed = Gtk.Fixed()
        self.fixed.set_hexpand(True)

        # Workspace text container
        self.workspaces_container = HBox(spacing=0)
        self.workspaces_container.set_name("workspaces-container")
        self.fixed.put(self.workspaces_container, 0, 0)

        # Initial update
        self.update(self.fixed)
        return self.fixed

    def update(self, widget: Gtk.Widget) -> None:
        """Update workspace display."""
        try:
            workspaces = self.wm_client.get_workspaces()
            if not workspaces:
                return

            # Check if any workspace is focused
            any_focused = any(ws.focused for ws in workspaces)

            # Clear all existing children from the container
            child = self.workspaces_container.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self.workspaces_container.remove(child)
                child = next_child
            self.workspace_widgets.clear()

            # Create workspace widgets
            for workspace in workspaces:
                # Create workspace button
                if self.show_labels:
                    label_text = workspace.name
                else:
                    label_text = ""

                ws_widget = Gtk.Label(label=label_text)
                ws_widget.set_name(f"workspace-{workspace.num}")
                ws_widget.set_size_request(16, -1)

                if (
                    workspace.focused or (workspace.num == 1 and not any_focused)
                ) and self.highlight_focused:
                    apply_styles(
                        ws_widget,
                        """
                        label {
                            background-color: #ebdbb2;
                            color: #0e1419;
                            border-radius: 2px;
                        }
                        """,
                    )

                # Add widget to container
                self.workspaces_container.append(ws_widget)
                self.workspace_widgets[workspace.num] = ws_widget

            # Container is shown by default in GTK4

        except Exception as e:
            print(f"Error updating workspaces: {e}")

    def setup_event_listeners(self, status_bar) -> List[Callable]:
        """Set up event listeners for workspace changes."""
        listeners = []

        if self.wm_client:
            # Create a callback that updates this module
            def workspace_callback():
                if self.fixed:
                    # Schedule update in main thread
                    from gi.repository import GLib

                    GLib.idle_add(self.update, self.fixed)

            try:
                self.wm_client.start_event_listener(workspace_callback)
                listeners.append(self.wm_client)
            except Exception as e:
                print(f"Error setting up workspace event listener: {e}")

        return listeners

    def get_size_mode(self) -> Tuple[StatusbarSizeMode, Optional[Tuple[int, int]]]:
        return StatusbarSizeMode.DEFAULT, None

    def get_styles(self) -> Optional[str]:
        return """
        #workspaces-container {
            padding: 0 8px;
        }

        #workspaces-container label {
            padding: 0;
            font-size: 12px;
            font-weight: 500;
            margin: 0 0;
            border-radius: 3px;
            transition: all 0.2s ease;
            color: #6272a4;
            background-color: transparent;
        }

        #workspaces-container label.urgent {
            color: #ff5555;
            background-color: rgba(255, 85, 85, 0.2);
        }

        #workspaces-container label.visible {
            color: #f8f8f2;
            background-color: rgba(248, 248, 242, 0.1);
        }
        """
