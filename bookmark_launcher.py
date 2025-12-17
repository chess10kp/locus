# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import webbrowser
from bookmarks import get_bookmarks
from hooks import LauncherHook


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
        # For now, no specific enter handling for bookmarks
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


class BookmarkLauncher:
    def __init__(self, launcher):
        self.launcher = launcher
        self.hook = BookmarkHook(launcher)
        launcher.hook_registry.register_hook(self.hook)

    def populate(self, query=""):
        bookmarks = get_bookmarks()
        if query:
            bookmarks = [b for b in bookmarks if query.lower() in b.lower()]
        actions = ["add", "remove", "replace"]
        all_items = bookmarks + actions
        for item in all_items:
            metadata = (
                self.launcher.METADATA.get("bookmark", "") if item in bookmarks else ""
            )
            button = self.launcher.create_button_with_metadata(item, metadata)
            self.launcher.list_box.append(button)
        self.launcher.current_apps = []
