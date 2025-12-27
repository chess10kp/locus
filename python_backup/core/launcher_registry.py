# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


class LauncherSizeMode(Enum):
    """Size modes for launcher windows."""

    DEFAULT = "default"
    WALLPAPER = "wallpaper"  # Larger size for wallpaper previews
    CUSTOM = "custom"
    GRID = "grid"  # Grid layout for custom launchers


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

    def get_grid_config(self) -> Optional[Dict[str, Any]]:
        """Return grid configuration if using grid mode.

        Returns:
            {
                'columns': int,           # Number of columns
                'item_width': int,        # Width of each grid item
                'item_height': int,       # Height of each grid item
                'spacing': int,           # Spacing between items
                'show_metadata': bool,    # Whether to show text metadata
                'metadata_position': str,  # 'bottom', 'overlay', 'hidden'
                'aspect_ratio': str,      # 'square', 'original', 'fixed'
            }
        """
        return None

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
        self._trigger_map: Dict[
            str, Any
        ] = {}  # Maps all prefixes (traditional + custom) to launchers
        self._original_triggers: Dict[
            str, Any
        ] = {}  # Maps normalized original triggers to launchers (legacy)

    def _is_custom_prefix_trigger(
        self, input_text: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Check if input matches a custom trigger pattern (colon or space suffix).

        Returns:
            Tuple of (trigger_string, prefix_type) or (None, None)
            where prefix_type is "colon" or "space"
        """
        if not input_text:
            return None, None

        # Check for colon-style triggers (e.g., "f:")
        if ":" in input_text:
            potential_trigger = input_text.split(":")[0]
            if potential_trigger in self._trigger_map:
                return potential_trigger, "colon"

        # Check for space-style triggers (e.g., "f query")
        if " " in input_text:
            potential_trigger = input_text.split(" ")[0]
            if potential_trigger in self._trigger_map:
                return potential_trigger, "space"

        return None, None

    def register(self, launcher: LauncherInterface) -> None:
        """Register a launcher plugin."""
        if launcher.name in self._launchers:
            raise ValueError(f"Launcher '{launcher.name}' is already registered")

        self._launchers[launcher.name] = launcher

        # Always register original triggers for traditional > matching
        for trigger in launcher.command_triggers:
            # Normalize: remove leading > if present
            normalized_trigger = trigger.lstrip(">")

            # Store in original triggers map for legacy support
            if normalized_trigger in self._original_triggers:
                existing = self._original_triggers[normalized_trigger]
                if isinstance(existing, list):
                    existing.append(launcher)
                else:
                    self._original_triggers[normalized_trigger] = [existing, launcher]
            else:
                self._original_triggers[normalized_trigger] = launcher

        # Check config for custom prefixes
        from core.config import LAUNCHER_PREFIXES

        if launcher.name in LAUNCHER_PREFIXES:
            # Use custom prefixes from config (ADDS to default triggers, doesn't replace)
            custom_triggers = LAUNCHER_PREFIXES[launcher.name]
            # Register custom triggers - extract trigger part only (remove colon/space)
            for trigger in custom_triggers:
                # For custom prefixes, extract just the trigger part (before colon/space)
                if ":" in trigger:
                    trigger_part = trigger.split(":")[0]
                elif " " in trigger:
                    trigger_part = trigger.split(" ")[0]
                else:
                    trigger_part = trigger

                if trigger_part in self._trigger_map:
                    # Allow multiple launchers with same trigger prefix
                    # but store them as a list for conflict resolution
                    existing = self._trigger_map[trigger_part]
                    if isinstance(existing, list):
                        existing.append(launcher)
                    else:
                        self._trigger_map[trigger_part] = [existing, launcher]
                else:
                    self._trigger_map[trigger_part] = launcher

        # Always register original triggers for traditional > matching
        for trigger in launcher.command_triggers:
            # Normalize: remove leading > if present
            normalized_trigger = trigger.lstrip(">")

            # Store in trigger map for O(1) lookup
            if normalized_trigger in self._trigger_map:
                existing = self._trigger_map[normalized_trigger]
                if isinstance(existing, list):
                    existing.append(launcher)
                else:
                    self._trigger_map[normalized_trigger] = [existing, launcher]
            else:
                self._trigger_map[normalized_trigger] = launcher

    def unregister(self, name: str) -> None:
        """Unregister a launcher by name."""
        if name not in self._launchers:
            return

        launcher = self._launchers[name]

        # Always remove from original triggers map
        for trigger in launcher.command_triggers:
            normalized_trigger = trigger.lstrip(">")
            if normalized_trigger in self._original_triggers:
                existing = self._original_triggers[normalized_trigger]
                if isinstance(existing, list):
                    self._original_triggers[normalized_trigger] = [
                        l for l in existing if l != launcher
                    ]
                    if len(self._original_triggers[normalized_trigger]) == 1:
                        self._original_triggers[normalized_trigger] = (
                            self._original_triggers[normalized_trigger][0]
                        )
                    elif len(self._original_triggers[normalized_trigger]) == 0:
                        del self._original_triggers[normalized_trigger]
                else:
                    del self._original_triggers[normalized_trigger]

        # Remove from custom trigger map
        from core.config import LAUNCHER_PREFIXES

        if launcher.name in LAUNCHER_PREFIXES:
            triggers = LAUNCHER_PREFIXES[launcher.name]
        else:
            triggers = launcher.command_triggers

        for trigger in triggers:
            normalized_trigger = trigger.lstrip(">")
            if normalized_trigger in self._trigger_map:
                existing = self._trigger_map[normalized_trigger]
                if isinstance(existing, list):
                    self._trigger_map[normalized_trigger] = [
                        l for l in existing if l != launcher
                    ]
                    if len(self._trigger_map[normalized_trigger]) == 1:
                        self._trigger_map[normalized_trigger] = self._trigger_map[
                            normalized_trigger
                        ][0]
                    elif len(self._trigger_map[normalized_trigger]) == 0:
                        del self._trigger_map[normalized_trigger]
                else:
                    del self._trigger_map[normalized_trigger]

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

    def find_launcher_for_input(
        self, input_text: str
    ) -> Tuple[Optional[str], Optional[LauncherInterface], str]:
        """Find launcher and remaining query for given input text.

        Supports three trigger styles:
        1. Traditional: ">file query" (with > prefix)
        2. Colon-style: "f: query" (custom with colon)
        3. Space-style: "f query" (custom with space)

        Returns:
            Tuple of (trigger_or_none, launcher_or_none, remaining_query)
        """
        if not input_text:
            return None, None, input_text

        # Check for traditional > prefix first
        if input_text.startswith(">"):
            # Remove the > prefix
            text_without_prefix = input_text[1:]

            # Use optimized hash lookup instead of linear search
            # Find the longest matching trigger from trigger map
            # This is O(1) instead of O(n log n) for sorted list
            longest_match = None
            longest_length = 0

            for trigger in self._trigger_map.keys():
                trigger_length = len(trigger)
                if (
                    trigger_length > longest_length
                    and trigger_length <= len(text_without_prefix)
                    and text_without_prefix.startswith(trigger)
                    and (
                        # Exact match (e.g., "wallpaper" matches "wallpaper")
                        text_without_prefix == trigger
                        or (
                            # Trigger followed by space (e.g., "wallpaper " matches "wallpaper")
                            len(text_without_prefix) > trigger_length
                            and text_without_prefix[trigger_length] == " "
                        )
                    )
                ):
                    longest_match = trigger
                    longest_length = trigger_length

            if longest_match:
                # Get launcher from trigger map
                launcher_result = self._trigger_map[longest_match]
                launcher = (
                    launcher_result[0]
                    if isinstance(launcher_result, list)
                    else launcher_result
                )
                remaining_query = text_without_prefix[len(longest_match) :].strip()
                return longest_match, launcher, remaining_query

            return None, None, input_text

        # Check for custom trigger patterns (colon or space)
        trigger, prefix_type = self._is_custom_prefix_trigger(input_text)

        if trigger and trigger in self._trigger_map:
            launcher = self.get_launcher_by_trigger(trigger)

            # Extract remaining query based on prefix type
            if prefix_type == "colon":
                # Remove "f:" to get remaining
                remaining_query = input_text[len(trigger) + 1 :].strip()
            else:  # space
                # Remove "f " to get remaining
                remaining_query = input_text[len(trigger) + 1 :].strip()

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
        return [
            (launcher.name, launcher.command_triggers)
            for launcher in self._launchers.values()
        ]


# Global registry instance
launcher_registry = LauncherRegistry()
