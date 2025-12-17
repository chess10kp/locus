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


class BookmarkLauncher:
    def __init__(self, launcher):
        self.launcher = launcher

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
            if item in bookmarks:
                button.connect("clicked", self.on_bookmark_clicked, item)
            else:
                button.connect("clicked", self.on_bookmark_action, item)
            self.launcher.list_box.append(button)
        self.launcher.current_apps = []

    def on_bookmark_clicked(self, button, bookmark):
        # Open bookmark in browser
        webbrowser.open(bookmark)
        self.launcher.hide()

    def on_bookmark_action(self, button, action):
        # For now, just print or do nothing
        print(f"Bookmark action: {action}")
        # Could implement dialogs here for add/remove
        self.launcher.hide()
