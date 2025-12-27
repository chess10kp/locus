# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

"""
Dmenu-style launcher that reads options from stdin and returns selection to stdout.

Supports both simple text lines and JSON metadata format.
Exits immediately after selection.
"""

import sys
import json
import logging
import os
from typing import List, Any, Tuple, Optional

from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode

logger = logging.getLogger("DmenuLauncher")


class DmenuItem:
    """Represents a dmenu item with optional metadata."""

    def __init__(self, title: str, subtitle: str = "", action_data: Any = None):
        self.title = title
        self.subtitle = subtitle
        self.action_data = action_data


class DmenuHook(LauncherHook):
    """Hook for handling dmenu selection."""

    def __init__(self, dmenu_launcher):
        self.dmenu_launcher = dmenu_launcher

    def on_select(self, launcher, item_data) -> bool:
        """Handle item selection - output to stdout or execute command."""
        if isinstance(item_data, dict) and item_data.get("type") == "dmenu_item":
            command = item_data.get("command", "")
            if command.startswith(">"):
                # Don't execute launcher commands
                return False
            if not sys.stdin.isatty():
                # Piped input, output command to stdout
                print(command, end="")
            else:
                # From client, execute the command
                import subprocess

                env = dict(os.environ.items())
                env.pop("LD_PRELOAD", None)
                subprocess.Popen(command, shell=True, env=env)
            # Exit immediately after selection
            sys.exit(0)
        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle enter key - use first available item."""
        # If there are items available, select the first one
        if self.dmenu_launcher.items:
            first_item = self.dmenu_launcher.items[0]
            command = (
                first_item.action_data if first_item.action_data else first_item.title
            )
            if command.startswith(">"):
                # Don't execute launcher commands
                return False
            if not sys.stdin.isatty():
                print(command, end="")
            else:
                import subprocess

                env = dict(os.environ.items())
                env.pop("LD_PRELOAD", None)
                subprocess.Popen(command, shell=True, env=env)
            sys.exit(0)
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle tab completion - not used for dmenu."""
        return None


class DmenuLauncher(LauncherInterface):
    """
    Dmenu-style launcher that reads options from stdin.

    Triggers: >dmenu, >dm
    Reads from stdin, displays options, returns selected command to stdout.
    Supports JSON metadata format: {"title": "...", "subtitle": "...", "command": "..."}
    """

    def __init__(self, main_launcher=None):
        self.items: List[DmenuItem] = []
        self.hook = DmenuHook(self)

        # Register hook with main launcher if available
        if main_launcher and hasattr(main_launcher, "hook_registry"):
            main_launcher.hook_registry.register_hook(self.hook)

        # Capture stdin if piped
        if not sys.stdin.isatty():
            self._capture_stdin()

    def set_options(self, options_str: str) -> None:
        """Set options from a string (for IPC)."""
        self.items = []
        self._parse_options(options_str)

    def _parse_options(self, options_str: str) -> None:
        """Parse options from string."""
        for line in options_str.split("\n"):
            line = line.rstrip("\n\r")
            if line.strip():
                self._parse_line(line)

    @property
    def command_triggers(self) -> List[str]:
        return ["dmenu", "dm"]

    @property
    def name(self) -> str:
        return "dmenu"

    def get_size_mode(self) -> Tuple[LauncherSizeMode, Optional[Tuple[int, int]]]:
        return (LauncherSizeMode.DEFAULT, None)

    def handles_enter(self) -> bool:
        return True

    def handle_enter(self, query: str, launcher_core) -> bool:
        """Handle enter key press - use first available item."""
        # If there are items available, select the first one
        if self.items:
            first_item = self.items[0]
            command = (
                first_item.action_data if first_item.action_data else first_item.title
            )
            print(command, end="")
            sys.exit(0)
        return False

    def _capture_stdin(self) -> None:
        """Capture and parse input from stdin."""
        try:
            if not sys.stdin.isatty():
                # Read all lines from stdin
                for line in sys.stdin:
                    line = line.rstrip("\n\r")
                    if line.strip():  # Skip empty lines
                        self._parse_line(line)
            else:
                # No stdin input - launcher will show help
                pass
        except Exception as e:
            logger.error(f"Error reading stdin: {e}")
            raise RuntimeError(f"Failed to read stdin input: {e}")

    def _parse_line(self, line: str) -> None:
        """Parse a single line, supporting both plain text and JSON metadata."""
        line = line.strip()
        if not line:
            return

        # Check if line looks like JSON (starts with {)
        if line.startswith("{"):
            try:
                # Try to parse as JSON
                data = json.loads(line)

                # Validate JSON structure
                if not isinstance(data, dict):
                    raise ValueError("JSON input must be an object")

                title = data.get("title", "").strip()
                if not title:
                    raise ValueError("JSON object must have a non-empty 'title' field")

                subtitle = data.get("subtitle", "").strip()
                command = data.get(
                    "command", title
                ).strip()  # Default to title if no command

                item = DmenuItem(title=title, subtitle=subtitle, action_data=command)
                self.items.append(item)

            except json.JSONDecodeError as e:
                # Malformed JSON - throw error as requested
                raise RuntimeError(f"Malformed JSON input: {line} - {str(e)}")
            except (ValueError, TypeError) as e:
                # Other validation errors - throw error as requested
                raise RuntimeError(f"Invalid JSON structure: {line} - {str(e)}")
        else:
            # Plain text line
            item = DmenuItem(title=line, action_data=line)
            self.items.append(item)

    def populate(self, query: str, launcher_core) -> None:
        """
        Populate launcher with dmenu options.

        Shows captured stdin items or help text.
        """
        if not self.items:
            # No items captured - show help
            launcher_core.add_launcher_result(
                "Dmenu Launcher",
                "Pipe options to stdin: echo -e 'option1\\noption2' | locus_client.py launcher dmenu",
                index=1,
                action_data={"type": "help"},
            )
            launcher_core.add_launcher_result(
                "JSON format supported",
                '{"title": "Option", "subtitle": "Description", "command": "cmd"}',
                index=2,
                action_data={"type": "help"},
            )
            return

        # Display items
        index = 1
        for item in self.items:
            action_data = {
                "type": "dmenu_item",
                "command": item.action_data if item.action_data else item.title,
            }

            launcher_core.add_launcher_result(
                item.title,
                item.subtitle if item.subtitle else "",
                index=index if index <= 9 else None,
                action_data=action_data,
            )

            index += 1
            if index > 50:  # Limit results for performance
                break

        # Scroll to top
        vadj = launcher_core.scrolled.get_vadjustment()
        if vadj:
            vadj.set_value(0)
        launcher_core.current_apps = []
