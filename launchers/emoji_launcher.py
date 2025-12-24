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
from typing import Any, Optional, List, Dict
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from utils.launcher_utils import LauncherEnhancer


class EmojiHook(LauncherHook):
    def __init__(self, emoji_launcher):
        self.emoji_launcher = emoji_launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """Handle emoji selection"""
        data_str = (
            item_data if isinstance(item_data, str) else str(item_data.get("", ""))
        )
        if len(data_str) == 1:  # Single emoji
            # Copy emoji to clipboard
            self.emoji_launcher.copy_to_clipboard(data_str)
            return True
        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle emoji enter key"""
        if text.startswith(">emoji"):
            # Just hide the launcher when enter is pressed
            return False
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle emoji tab completion"""
        if text.startswith(">emoji"):
            return " "
        return None


class EmojiLauncher(LauncherInterface):
    @classmethod
    def check_dependencies(cls) -> tuple[bool, str]:
        """Check if required dependencies are available.

        Returns:
            Tuple of (available, error_message)
        """
        from utils import check_clipboard

        if not check_clipboard():
            return False, "clipboard utility (wl-copy or xclip) not found"
        return True, ""

    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.hook = EmojiHook(self)
        self.emoji_data = []
        self.load_emoji_data()

        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, "hook_registry"):
            main_launcher.hook_registry.register_hook(self.hook)

    def load_emoji_data(self) -> None:
        """Load emoji data from the emojis.txt file."""
        emoji_file = os.path.join(os.path.dirname(__file__), "emojis.txt")
        if os.path.exists(emoji_file):
            try:
                with open(emoji_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:  # Non-empty line
                            # Extract emoji character (first character)
                            emoji_char = line[0]
                            # Extract keywords (rest of the line after the emoji)
                            keywords = line[1:].split()
                            self.emoji_data.append(
                                {"emoji": emoji_char, "keywords": keywords}
                            )
            except Exception as e:
                print(f"Error loading emoji data: {e}")

    @property
    def command_triggers(self):
        return ["emoji", "em", "emj", "e"]

    @property
    def name(self):
        return "emoji"

    def get_size_mode(self):
        return LauncherSizeMode.DEFAULT, None

    def handles_enter(self):
        return False

    def handle_enter(self, query: str, launcher_core) -> bool:
        return False

    def search_emojis(self, query: str) -> List[Dict]:
        """Search for emojis by keywords."""
        if not query:
            return self.emoji_data[:50]  # Return first 50 by default

        query = query.lower()
        results = []

        for emoji_data in self.emoji_data:
            if any(query in keyword.lower() for keyword in emoji_data["keywords"]):
                results.append(emoji_data)

        return results[:50]  # Limit results

    def populate(self, query: str, launcher_core):
        """Populate the launcher with emojis."""
        emojis = self.search_emojis(query)

        if not emojis:
            launcher_core.add_launcher_result("No emojis found", "", index=1)
            return

        # Add each emoji as an individual result item
        index = 1
        for emoji_data in emojis:
            if index > 9:  # Limit to first 9 results for Alt+1-9 shortcuts
                break

            # Use emoji as title, no subtitle (metadata)
            title = emoji_data["emoji"]

            launcher_core.add_launcher_result(
                title=title,
                subtitle="",  # Empty subtitle - no metadata
                index=index,
                action_data=emoji_data["emoji"],
            )
            index += 1

    def copy_to_clipboard(self, text: str):
        """Copy text to clipboard."""
        try:
            # Clean environment for child processes
            env = dict(os.environ.items())
            env.pop("LD_PRELOAD", None)  # Remove LD_PRELOAD for child processes

            # Try wl-copy first (Wayland)
            try:
                subprocess.run(["wl-copy"], input=text.encode(), check=True, env=env)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback to xclip (X11)
                try:
                    subprocess.run(
                        ["xclip", "-selection", "clipboard"],
                        input=text.encode(),
                        check=True,
                        env=env,
                    )
                except (subprocess.CalledProcessError, FileNotFoundError):
                    print(f"Failed to copy to clipboard: {text}")

        except Exception as e:
            print(f"Error copying to clipboard: {e}")

        if self.launcher:
            self.launcher.hide()
