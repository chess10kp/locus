# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import json
import os
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


@dataclass
class LauncherState:
    """Represents the saved state of the launcher."""

    search_text: str
    selected_index: int
    active_launcher_context: str
    timestamp: str
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LauncherState":
        """Create from dictionary (JSON deserialization)."""
        return cls(**data)


class LauncherStateManager:
    """Manages saving and loading of launcher state."""

    _instance: Optional["LauncherStateManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure only one manager exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, persist_path: Optional[str] = None):
        """Initialize the launcher state manager.

        Args:
            persist_path: Path to JSON file for persistence
        """
        # Avoid re-initializing if already initialized
        if hasattr(self, "_initialized"):
            return

        self._lock = threading.RLock()

        # Set up persistence path
        if persist_path is None:
            cache_dir = Path.home() / ".cache" / "locus"
            cache_dir.mkdir(parents=True, exist_ok=True)
            persist_path = str(cache_dir / "launcher_state.json")

        self.persist_path = persist_path
        self._initialized = True

    def save_state(
        self, search_text: str, selected_index: int, active_launcher_context: str
    ) -> bool:
        """Save the current launcher state.

        Args:
            search_text: Current search query text
            selected_index: Index of selected item (uint from selection_model)
            active_launcher_context: Current launcher context ("apps", "command", or launcher name)

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            try:
                state = LauncherState(
                    search_text=search_text,
                    selected_index=selected_index,
                    active_launcher_context=active_launcher_context,
                    timestamp=datetime.now().isoformat(),
                )
                data = {
                    "state": state.to_dict(),
                    "version": 1,
                }
                with open(self.persist_path, "w") as f:
                    json.dump(data, f, indent=2)
                return True
            except Exception as e:
                print(f"Error saving launcher state: {e}")
                return False

    def load_state(self) -> Optional[Dict[str, Any]]:
        """Load the saved launcher state.

        Returns:
            Dict containing state data, or None if no state exists or error
        """
        with self._lock:
            try:
                if not os.path.exists(self.persist_path):
                    return None

                with open(self.persist_path, "r") as f:
                    data = json.load(f)

                # Load state
                if "state" in data:
                    state_data = data["state"]
                    state = LauncherState.from_dict(state_data)
                    return {
                        "search_text": state.search_text,
                        "selected_index": state.selected_index,
                        "active_launcher_context": state.active_launcher_context,
                        "timestamp": state.timestamp,
                    }

                return None
            except Exception as e:
                print(f"Error loading launcher state: {e}")
                return None

    def clear_state(self) -> bool:
        """Clear the saved launcher state.

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            try:
                if os.path.exists(self.persist_path):
                    os.remove(self.persist_path)
                return True
            except Exception as e:
                print(f"Error clearing launcher state: {e}")
                return False


# Singleton accessor function
_launcher_state_manager_instance: Optional[LauncherStateManager] = None


def get_launcher_state() -> LauncherStateManager:
    """Get the singleton launcher state manager instance."""
    global _launcher_state_manager_instance
    if _launcher_state_manager_instance is None:
        _launcher_state_manager_instance = LauncherStateManager()
    return _launcher_state_manager_instance
