# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import webbrowser
from utils import get_bookmarks
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from typing import Optional, Tuple


class BookmarkHook(LauncherHook):
    def __init__(self, launcher):
        self.launcher = launcher

    def on_select(self, launcher, item_data):
        """Handle button clicks for bookmarks and actions."""
        if not item_data:
            return False

        bookmarks = get_bookmarks()
        if item_data in bookmarks:
            # Open bookmark in browser
            webbrowser.open(item_data)
            launcher.hide()
            return True
        elif item_data in ["add", "remove", "replace"]:
            # Handle bookmark actions
            print(f"Bookmark action: {item_data}")
            # Could implement dialogs here for add/remove
            launcher.hide()
            return True

        return False

    def on_enter(self, launcher, text):
        """Handle enter key for bookmark operations."""
        webbrowser.open(text)
        return False

    def on_tab(self, launcher, text):
        """Handle tab completion for bookmarks."""
        bookmarks = get_bookmarks()
        matching_bookmarks = [
            b for b in bookmarks if b.lower().startswith(text.lower())
        ]

        if matching_bookmarks:
            # Return first match for tab completion
            return matching_bookmarks[0]

        return None


class BookmarkLauncher(LauncherInterface):
    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.hook = BookmarkHook(self)

        # Register with launcher registry
        from core.launcher_registry import launcher_registry
        launcher_registry.register(self)

        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, 'hook_registry'):
            main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self):
        return ["bookmark"]

    @property
    def name(self):
        return "bookmark"

    def get_size_mode(self):
        return LauncherSizeMode.DEFAULT, None

    def handles_tab(self):
        return True

    def handle_tab(self, query: str, launcher_core) -> Optional[str]:
        """Handle tab completion for bookmarks."""
        bookmarks = get_bookmarks()
        matching_bookmarks = [
            b for b in bookmarks if b.lower().startswith(query.lower())
        ]
        if matching_bookmarks:
            return matching_bookmarks[0]
        return None

    def populate(self, query, launcher_core):
        bookmarks = get_bookmarks()
        if query:
            bookmarks = [b for b in bookmarks if query.lower() in b.lower()]
        actions = ["add", "remove", "replace"]
        all_items = bookmarks + actions
        for item in all_items:
            metadata = (
                launcher_core.METADATA.get("bookmark", "") if item in bookmarks else ""
            )
            button = launcher_core.create_button_with_metadata(item, metadata)
            launcher_core.list_box.append(button)
        launcher_core.current_apps = []
