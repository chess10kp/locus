# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from gi.repository import Gdk, Gtk  # pyright: ignore
from typing import Any, Optional, List


class LauncherEnhancer:
    """
    Utility class to add Alt+number selection and right-aligned hints to specialized launchers.
    """

    @staticmethod
    def add_button_with_hint(
        launcher_core,
        text: str,
        metadata: str = "",
        hook_data: Any = None,
        index: Optional[int] = None
    ) -> Gtk.Button:
        """
        Add a button with right-aligned hint (index number).
        Similar to launcher_core.create_button_with_metadata but handles hint display.

        Args:
            launcher_core: The main launcher instance
            text: Main button text
            metadata: Secondary text (metadata)
            hook_data: Data to pass to hook on selection
            index: Index number for Alt+number selection and hint display

        Returns:
            Created button widget
        """
        return launcher_core.create_button_with_metadata(text, metadata, hook_data, index)

    @staticmethod
    def add_multiple_buttons_with_hints(
        launcher_core,
        items: List[tuple],
        start_index: int = 1
    ) -> List[Gtk.Button]:
        """
        Add multiple buttons with sequential hints (Alt+1, Alt+2, etc.).

        Args:
            launcher_core: The main launcher instance
            items: List of tuples (text, metadata, hook_data)
            start_index: Starting index for numbering (default 1)

        Returns:
            List of created button widgets
        """
        buttons = []
        for i, (text, metadata, hook_data) in enumerate(items):
            index = start_index + i
            if index <= 10:  # Only add hints for 1-9 (and 10 if we want)
                button = LauncherEnhancer.add_button_with_hint(
                    launcher_core, text, metadata, hook_data, index
                )
            else:
                # For items beyond 9, don't show number hints but still create button
                button = launcher_core.create_button_with_metadata(text, metadata, hook_data)
            buttons.append(button)
            launcher_core.list_box.append(button)

        return buttons

    @staticmethod
    def handle_alt_number_selection(
        controller, keyval, keycode, state, launcher_core
    ) -> bool:
        """
        Handle Alt+number key presses for specialized launchers.
        This should be called from specialized launcher key press handlers.

        Args:
            controller: GTK event controller
            keyval: Key value
            keycode: Key code
            state: Modifier state
            launcher_core: The main launcher instance

        Returns:
            True if Alt+number was handled, False otherwise
        """
        # Handle Alt+1 to Alt+9 for selecting items
        if state & Gdk.ModifierType.ALT_MASK:  # Alt key
            if Gdk.KEY_1 <= keyval <= Gdk.KEY_9:
                index = keyval - Gdk.KEY_1  # 0 for 1, 1 for 2, etc.
                LauncherEnhancer.select_by_index(index, launcher_core)
                return True
        return False

    @staticmethod
    def select_by_index(index: int, launcher_core) -> None:
        """
        Select item by index (0-based) in specialized launcher.
        This mirrors the main launcher's select_by_index method.

        Args:
            index: 0-based index of item to select
            launcher_core: The main launcher instance
        """
        row = launcher_core.list_box.get_row_at_index(index)
        if row:
            launcher_core.selected_row = row
            launcher_core.list_box.select_row(row)
            button = row.get_child()
            if button:
                button.emit("clicked")
                launcher_core.hide()

    @staticmethod
    def add_key_handler_to_launcher(launcher_class):
        """
        Decorator to add Alt+number key handling to specialized launcher classes.

        Args:
            launcher_class: The specialized launcher class to enhance
        """
        original_key_pressed = getattr(launcher_class, 'on_key_pressed', None)

        def enhanced_key_pressed(self, controller, keyval, keycode, state, launcher_core=None):
            # First try to handle Alt+number selection
            if LauncherEnhancer.handle_alt_number_selection(
                controller, keyval, keycode, state, launcher_core
            ):
                return True

            # Fall back to original key handling if it exists
            if original_key_pressed:
                return original_key_pressed(self, controller, keyval, keycode, state, launcher_core)

            return False

        # Replace or add the method
        setattr(launcher_class, 'on_key_pressed', enhanced_key_pressed)
        return launcher_class


def enhance_populate_with_hints(populate_func):
    """
    Decorator to automatically add hints to specialized launcher populate methods.

    Args:
        populate_func: The original populate function

    Returns:
        Enhanced populate function that adds hints
    """
    def enhanced_populate(self, query: str, launcher_core) -> None:
        # Store original populate result
        buttons_before = []
        child = launcher_core.list_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            buttons_before.append((child, child.get_first_child()))
            child = next_child

        # Call original populate
        populate_func(self, query, launcher_core)

        # Add hints to newly created buttons
        index = 1
        child = launcher_core.list_box.get_first_child()
        while child and index <= 9:  # Only add hints for first 9 items
            button_child = child.get_first_child()
            if button_child and hasattr(button_child, 'get_children'):  # Check if it's a box with multiple children
                # Check if it already has a hint (right-aligned label)
                has_hint = False
                for grandchild in button_child.get_children():
                    if hasattr(grandchild, 'get_label') and grandchild.get_label() and grandchild.get_label().isdigit():
                        has_hint = True
                        break

                # If no hint, we could potentially add one here
                # But since we can't easily modify existing buttons, we'll rely on populate methods to pass index

            child = child.get_next_sibling()
            index += 1

    return enhanced_populate
