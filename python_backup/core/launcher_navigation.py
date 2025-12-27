# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import logging
from gi.repository import Gdk, GLib, Gtk
from .config import (
    CUSTOM_LAUNCHERS,
    LAUNCHER_CONFIG,
    LAUNCHER_PREFIXES,
    LAUNCHER_PREFIX_SHORTCUTS,
)
from .process_launcher import handle_custom_launcher
from utils.key_binding_parser import parse_key_bindings, key_matches

logger = logging.getLogger("LauncherNavigation")


class LauncherNavigation:
    """Manages keyboard navigation for Launcher."""

    def __init__(self, launcher):
        self.launcher = launcher

        # Parse key bindings from config
        self.parsed_key_bindings = {}
        for action, bindings in LAUNCHER_CONFIG.get("keys", {}).items():
            self.parsed_key_bindings[action] = parse_key_bindings(bindings)

        # Parse prefix shortcuts
        self.parsed_prefix_shortcuts = {}
        for binding, launcher_name in LAUNCHER_PREFIX_SHORTCUTS.items():
            self.parsed_prefix_shortcuts[launcher_name] = parse_key_bindings([binding])[
                0
            ]

    def select_next(self):
        """Select the next item in the optimized ListView."""
        n_items = self.launcher.list_store.get_n_items()
        if n_items == 0:
            return

        current_selected = self.launcher.selection_model.get_selected()
        new_position = current_selected

        if current_selected == Gtk.INVALID_LIST_POSITION:
            # No selection, select the first item
            new_position = 0
            self.launcher.selection_model.set_selected(0)
        elif current_selected < n_items - 1:
            # Select the next item
            new_position = current_selected + 1
            self.launcher.selection_model.set_selected(new_position)

        if new_position != Gtk.INVALID_LIST_POSITION:
            self.launcher.list_view.scroll_to(new_position, Gtk.ListScrollFlags.NONE)

        self.launcher.search_entry.grab_focus()
        self.launcher.search_entry.set_position(-1)

    def select_prev(self):
        """Select the previous item in the optimized ListView."""
        n_items = self.launcher.list_store.get_n_items()
        if n_items == 0:
            return

        current_selected = self.launcher.selection_model.get_selected()
        new_position = current_selected

        if current_selected == Gtk.INVALID_LIST_POSITION:
            # No selection, focus search entry
            self.launcher.search_entry.grab_focus()
            self.launcher.search_entry.set_position(-1)
        elif current_selected > 0:
            # Select previous item
            new_position = current_selected - 1
            self.launcher.selection_model.set_selected(new_position)
            # Scroll to the selected item to ensure it's visible (like arrow keys do)
            self.launcher.list_view.scroll_to(new_position, Gtk.ListScrollFlags.NONE)
            # Focus the search entry for better UX
            self.launcher.search_entry.grab_focus()
            self.launcher.search_entry.set_position(-1)
        else:
            # At first item, jump back to search entry
            self.launcher.selection_model.unselect_all()
            self.launcher.search_entry.grab_focus()
            self.launcher.search_entry.set_position(-1)

    def select_by_index(self, index):
        """Select the item at the given index (0-based) and activate it."""
        n_items = self.launcher.list_store.get_n_items()
        if index < 0 or index >= n_items:
            return

        search_result = self.launcher.list_store.get_item(index)
        if search_result:
            # Handle the action directly for Alt+number shortcuts
            if search_result.result_type.name == "LAUNCHER":
                self.launcher.hide()
                if search_result.action_data:
                    self.launcher.hook_registry.execute_select_hooks(
                        self.launcher, search_result.action_data
                    )
                else:
                    self.on_command_selected(None, search_result.command)
            else:
                self.launcher._on_list_item_clicked(None, search_result)

    def yank_by_index(self, index):
        """Yank (copy) the item at the given index (0-based) to clipboard."""
        n_items = self.launcher.list_store.get_n_items()
        if index < 0 or index >= n_items:
            return

        search_result = self.launcher.list_store.get_item(index)
        if search_result:
            # Determine what text to copy based on result type
            text_to_copy = None

            if search_result.result_type.name == "APP":
                # For apps, copy the app name
                text_to_copy = search_result.title
            elif search_result.result_type.name == "COMMAND":
                # For commands, copy the command text (remove "Run: " prefix)
                if search_result.title.startswith("Run: "):
                    text_to_copy = search_result.title[5:]
                else:
                    text_to_copy = search_result.title
            elif search_result.result_type.name == "LAUNCHER":
                # For launchers, copy the launcher command (e.g., ">music")
                text_to_copy = search_result.title
            elif search_result.result_type.name == "CUSTOM":
                # For custom results, copy the title
                text_to_copy = search_result.title

            if text_to_copy:
                # Copy to clipboard
                from utils.clipboard import copy_to_clipboard

                success = copy_to_clipboard(text_to_copy)

                if success:
                    # Close the launcher window after yanking
                    self.launcher.hide()
                    # Show brief feedback
                    self._show_yank_feedback(text_to_copy)
                else:
                    pass

    def _get_launcher_prefix(self, launcher_name: str) -> str:
        """Get the prefix string to type for a launcher name.

        Uses custom prefix if available, otherwise falls back to >name + space.
        """
        if launcher_name in LAUNCHER_PREFIXES:
            # Use first custom prefix
            prefix = LAUNCHER_PREFIXES[launcher_name][0]
            # Add space if not already present
            return prefix if prefix.endswith(" ") else prefix + " "
        else:
            return f">{launcher_name} "

    def _handle_prefix_shortcut(self, launcher_name: str):
        """Handle a prefix shortcut by typing the prefix into the search entry."""
        prefix = self._get_launcher_prefix(launcher_name)
        self.launcher.search_entry.set_text(prefix)
        self.launcher.search_entry.set_position(-1)  # Move cursor to end

    def _show_yank_feedback(self, text: str, duration_ms: int = 500):
        """Show brief feedback when text is yanked to clipboard.

        Args:
            text: The text that was yanked
            duration_ms: How long to show the feedback
        """
        # Truncate text if too long
        display_text = text if len(text) <= 40 else text[:37] + "..."

        # Show feedback in the search entry temporarily
        original_text = self.launcher.search_entry.get_text()
        placeholder_text = self.launcher.search_entry.get_placeholder_text()

        # Set the search entry to show yanked text
        self.launcher.search_entry.set_text(f"Yanked: {display_text}")
        self.launcher.search_entry.set_editable(False)

        # Restore original state after duration
        def restore_search_entry():
            self.launcher.search_entry.set_editable(True)
            self.launcher.search_entry.set_text(original_text)
            if placeholder_text:
                self.launcher.search_entry.set_placeholder_text(placeholder_text)

        # Schedule restoration
        GLib.timeout_add(duration_ms, restore_search_entry)

    def on_app_clicked(self, button, app):
        """Handle app button click."""
        self.launcher.launch_app(app)

    def on_command_clicked(self, button, command):
        """Handle command button click."""
        self.launcher.run_command(command)

    def on_custom_launcher_clicked(self, button, command):
        """Handle custom launcher button click."""
        if handle_custom_launcher(command, self.launcher.apps, self.launcher):
            self.launcher.hide()

    def _handle_tab_complete(self):
        """Handle tab completion logic."""
        text = self.launcher.search_entry.get_text()

        # Try hooks first
        result = self.launcher.hook_registry.execute_tab_hooks(self.launcher, text)
        if result is not None:
            self.launcher.search_entry.set_text(result)
            self.launcher.search_entry.set_position(-1)
            return True

        # Check if any registered launcher can handle tab completion
        trigger, launcher, query = (
            self.launcher.launcher_registry.find_launcher_for_input(text)
        )
        if launcher and launcher.handles_tab():
            completion = launcher.handle_tab(query, self.launcher)
            if completion:
                # Return the full command with completion
                self.launcher.search_entry.set_text(f">{trigger}{completion}")
                self.launcher.search_entry.set_position(-1)
                return True

        # Fall back to command completion from registry
        if text.startswith(">"):
            command = text[1:].strip()
            all_commands = self.launcher.launcher_registry.get_all_triggers() + list(
                CUSTOM_LAUNCHERS.keys()
            )
            if not command:
                # No command yet, complete to first available
                if all_commands:
                    first_cmd = all_commands[0]
                    is_launcher_trigger = (
                        first_cmd in self.launcher.launcher_registry.get_all_triggers()
                    )
                    suffix = " " if is_launcher_trigger else ""
                    self.launcher.search_entry.set_text(f">{first_cmd}{suffix}")
                    self.launcher.search_entry.set_position(-1)
                    return True
            else:
                # Partial command, find matching
                matching = [cmd for cmd in all_commands if cmd.startswith(command)]
                if matching:
                    cmd = matching[0]
                    is_launcher_trigger = (
                        cmd in self.launcher.launcher_registry.get_all_triggers()
                    )
                    suffix = " " if is_launcher_trigger else ""
                    self.launcher.search_entry.set_text(f">{cmd}{suffix}")
                    self.launcher.search_entry.set_position(-1)
                    return True
        elif self.launcher.current_apps:
            # App mode, complete to first app
            self.launcher.search_entry.set_text(self.launcher.current_apps[0]["name"])
            self.launcher.search_entry.set_position(-1)
            return True
        return True  # Prevent default tab behavior

    def on_command_selected(self, button, command):
        """Handle command selection."""
        # Set the search entry to >command and trigger activate
        if command in [
            "calc",
            "bookmark",
            "bluetooth",
            "wifi",
            "wallpaper",
            "timer",
            "kill",
            "mpd",
            "refile",
        ]:
            self.launcher.search_entry.set_text(f">{command} ")
        elif command == "lock":
            self.launcher.search_entry.set_text(f">{command}")
        else:
            self.launcher.search_entry.set_text(f">{command}")
        self.launcher.on_entry_activate(self.launcher.search_entry)

    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle keyboard shortcuts."""
        # Check for prefix shortcuts first
        for launcher_name, parsed_binding in self.parsed_prefix_shortcuts.items():
            if key_matches(keyval, state, [parsed_binding]):
                self._handle_prefix_shortcut(launcher_name)
                return True

        # Handle Alt+1 to Alt+9 for selecting items
        if state & Gdk.ModifierType.ALT_MASK:  # Alt key
            if Gdk.KEY_1 <= keyval <= Gdk.KEY_9:
                index = keyval - Gdk.KEY_1  # 0 for 1, 1 for 2, etc.
                self.select_by_index(index)
                return True

        # Handle Ctrl+1 to Ctrl+9 for yanking (copying) items
        if state & Gdk.ModifierType.CONTROL_MASK:  # Ctrl key
            if Gdk.KEY_1 <= keyval <= Gdk.KEY_9:
                index = keyval - Gdk.KEY_1  # 0 for 1, 1 for 2, etc.
                self.yank_by_index(index)
                return True

        # Handle tab completion
        if key_matches(keyval, state, self.parsed_key_bindings.get("tab_complete", [])):
            return self._handle_tab_complete()

        # Handle navigation keys using config
        if key_matches(keyval, state, self.parsed_key_bindings.get("up", [])):
            self.select_prev()
            return True
        if key_matches(keyval, state, self.parsed_key_bindings.get("down", [])):
            self.select_next()
            return True

        # Handle activation
        if key_matches(keyval, state, self.parsed_key_bindings.get("activate", [])):
            self.launcher.on_entry_activate(self.launcher.search_entry)
            return True

        # Handle close/escape
        if key_matches(keyval, state, self.parsed_key_bindings.get("close", [])):
            self.launcher.hide()
            return True

        return False
