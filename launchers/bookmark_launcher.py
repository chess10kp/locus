# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import os
import subprocess
from utils import get_bookmarks, remove_bookmark
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from typing import Optional


class BookmarkHook(LauncherHook):
    def __init__(self, launcher):
        self.launcher = launcher

    def on_select(self, launcher, item_data):
        """Handle button clicks for bookmarks and actions."""
        if not item_data:
            return False

        bookmarks = get_bookmarks()
        if self.launcher.remove_mode and item_data in bookmarks:
            # Remove the bookmark
            remove_bookmark(item_data)
            self.launcher.remove_mode = False
            launcher.hide()
            return True
        elif item_data in bookmarks:
            # Open bookmark in default browser
            print(f"Opening bookmark with xdg-open: {item_data}")
            try:
                env = os.environ.copy()
                env.pop(
                    "MALLOC_PERTURB_", None
                )  # Remove malloc perturb for child processes
                env.pop("LD_PRELOAD", None)  # Remove LD_PRELOAD for child processes
                # Clean GTK/GDK environment variables to prevent crashes in child processes
                gtk_gdk_keys = [k for k in env if k.startswith(("GTK_", "GDK_"))]
                for key in gtk_gdk_keys:
                    env.pop(key, None)

                # Use xdg-open to open in the default browser
                result = subprocess.Popen(
                    ["xdg-open", item_data], start_new_session=True, env=env
                )
                print(f"subprocess.Popen returned: {result}")
            except Exception as e:
                print(f"Failed to open bookmark: {e}")
            launcher.hide()
            return True
        elif item_data in ["add", "replace"]:
            # Handle other bookmark actions
            print(f"Bookmark action: {item_data}")
            # Could implement dialogs here for add/replace
            launcher.hide()
            return True

        return False

    def on_enter(self, launcher, text):
        """Handle enter key for bookmark operations."""
        try:
            env = os.environ.copy()
            env.pop(
                "MALLOC_PERTURB_", None
            )  # Remove malloc perturb for child processes

            # Use xdg-open to open in the default browser
            subprocess.Popen(["xdg-open", text], start_new_session=True, env=env)
        except Exception as e:
            print(f"Failed to open URL: {e}")
        return False

    def on_tab(self, launcher, text):
        """Handle tab completion for bookmarks."""
        # Only handle bookmark commands
        if not text.startswith(">bookmark"):
            return None

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
        self.remove_mode = False
        self.hook = BookmarkHook(self)

        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, "hook_registry"):
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
        if self.remove_mode:
            # In remove mode, show all bookmarks for selection, no filter
            all_items = bookmarks
        else:
            if query == "remove":
                # Enter remove mode when typing ">bookmark remove"
                self.remove_mode = True
                all_items = bookmarks
            else:
                if query:
                    bookmarks = [b for b in bookmarks if query.lower() in b.lower()]
                actions = ["add", "replace"]  # "remove" requires typing "remove"
                all_items = bookmarks + actions
        index = 1
        for item in all_items:
            metadata = (
                launcher_core.METADATA.get("bookmark", "") if item in bookmarks else ""
            )
            launcher_core.add_launcher_result(
                item, metadata, index=index if index <= 9 else None, action_data=item
            )
            index += 1
            if index > 9:  # Stop showing hints after 9
                break
        launcher_core.current_apps = []
