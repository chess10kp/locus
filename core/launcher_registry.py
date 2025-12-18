# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple, Callable
from enum import Enum


class LauncherSizeMode(Enum):
    """Size modes for launcher windows."""
    DEFAULT = "default"
    WALLPAPER = "wallpaper"  # Larger size for wallpaper previews
    CUSTOM = "custom"


class LauncherInterface(ABC):
    """Abstract interface that all launchers must implement."""

    @property
    @abstractmethod
    def command_triggers(self) -> List[str]:
        """Return list of command prefixes that trigger this launcher (e.g., ['>calc', '>calculator'])."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of this launcher."""
        pass

    @abstractmethod
    def populate(self, query: str, launcher_core) -> None:
        """Populate the launcher UI with results based on the query.

        Args:
            query: The command/query string (without the trigger prefix)
            launcher_core: Reference to the main launcher for UI operations
        """
        pass

    @abstractmethod
    def get_size_mode(self) -> Tuple[LauncherSizeMode, Optional[Tuple[int, int]]]:
        """Return the size mode and optional custom size for this launcher.

        Returns:
            Tuple of (size_mode, optional_custom_size)
        """
        pass

    def handles_enter(self) -> bool:
        """Return True if this launcher wants to handle enter key presses."""
        return False

    def handle_enter(self, query: str, launcher_core) -> bool:
        """Handle enter key press. Return True if handled, False otherwise.
        Only called if handles_enter() returns True.
        """
        return False

    def handles_tab(self) -> bool:
        """Return True if this launcher wants to handle tab completion."""
        return False

    def handle_tab(self, query: str, launcher_core) -> Optional[str]:
        """Handle tab completion. Return completion string or None.
        Only called if handles_tab() returns True.
        """
        return None

    def cleanup(self) -> None:
        """Clean up resources when launcher is being unregistered."""
        pass


class LauncherRegistry:
    """Central registry for managing launcher plugins."""

    def __init__(self):
        self._launchers: Dict[str, LauncherInterface] = {}
        self._trigger_map: Dict[str, LauncherInterface] = {}

    def register(self, launcher: LauncherInterface) -> None:
        """Register a launcher plugin."""
        if launcher.name in self._launchers:
            raise ValueError(f"Launcher '{launcher.name}' is already registered")

        self._launchers[launcher.name] = launcher

        # Register command triggers
        for trigger in launcher.command_triggers:
            if trigger in self._trigger_map:
                # Allow multiple launchers with same trigger prefix
                # but store them as a list for conflict resolution
                existing = self._trigger_map[trigger]
                if isinstance(existing, list):
                    existing.append(launcher)
                else:
                    self._trigger_map[trigger] = [existing, launcher]
            else:
                self._trigger_map[trigger] = launcher

    def unregister(self, name: str) -> None:
        """Unregister a launcher by name."""
        if name not in self._launchers:
            return

        launcher = self._launchers[name]

        # Remove from trigger map
        for trigger in launcher.command_triggers:
            if trigger in self._trigger_map:
                existing = self._trigger_map[trigger]
                if isinstance(existing, list):
                    self._trigger_map[trigger] = [l for l in existing if l != launcher]
                    if len(self._trigger_map[trigger]) == 1:
                        self._trigger_map[trigger] = self._trigger_map[trigger][0]
                    elif len(self._trigger_map[trigger]) == 0:
                        del self._trigger_map[trigger]
                else:
                    del self._trigger_map[trigger]

        # Cleanup and remove launcher
        launcher.cleanup()
        del self._launchers[name]

    def get_launcher_by_trigger(self, trigger: str) -> Optional[LauncherInterface]:
        """Get launcher instance by command trigger."""
        if trigger in self._trigger_map:
            result = self._trigger_map[trigger]
            return result[0] if isinstance(result, list) else result
        return None

    def get_matching_launchers(self, trigger: str) -> List[LauncherInterface]:
        """Get all launchers that match a trigger prefix."""
        if trigger in self._trigger_map:
            result = self._trigger_map[trigger]
            return result if isinstance(result, list) else [result]
        return []

    def find_launcher_for_input(self, input_text: str) -> Tuple[Optional[str], Optional[LauncherInterface], str]:
        """Find launcher and remaining query for given input text.

        Returns:
            Tuple of (trigger_or_none, launcher_or_none, remaining_query)
        """
        if not input_text or not input_text.startswith(">"):
            return None, None, input_text

        # Remove the > prefix
        text_without_prefix = input_text[1:]

        # Find the longest matching trigger
        sorted_triggers = sorted(self._trigger_map.keys(), key=len, reverse=True)

        for trigger in sorted_triggers:
            if text_without_prefix.startswith(trigger):
                launcher = self.get_launcher_by_trigger(trigger)
                remaining_query = text_without_prefix[len(trigger):].strip()
                return trigger, launcher, remaining_query

        return None, None, input_text

    def get_all_triggers(self) -> List[str]:
        """Get all registered command triggers."""
        return list(self._trigger_map.keys())

    def get_all_launchers(self) -> List[LauncherInterface]:
        """Get all registered launchers."""
        return list(self._launchers.values())

    def list_launchers(self) -> List[Tuple[str, List[str]]]:
        """Get list of (launcher_name, command_triggers) for all launchers."""
        return [(launcher.name, launcher.command_triggers) for launcher in self._launchers.values()]


# Global registry instance
launcher_registry = LauncherRegistry()