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
import subprocess
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from utils.launcher_utils import LauncherEnhancer


class ClipboardHistoryStore:
    """Singleton class for managing clipboard history timestamps."""

    _instance: Optional["ClipboardHistoryStore"] = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure only one store exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        max_age_days: int = 30,
        persist_path: Optional[str] = None,
    ):
        """Initialize the clipboard history store.

        Args:
            max_age_days: Maximum age in days before cleanup
            persist_path: Path to JSON file for persistence
        """
        # Avoid re-initializing if already initialized
        if hasattr(self, "_initialized"):
            return

        self.max_age_days = max_age_days
        self.timestamps: Dict[str, datetime] = {}
        self._lock = threading.RLock()

        # Set up persistence path
        if persist_path is None:
            cache_dir = os.path.expanduser("~/.cache/locus")
            os.makedirs(cache_dir, exist_ok=True)
            persist_path = os.path.join(cache_dir, "clipboard_timestamps.json")

        self.persist_path = persist_path

        # Load from disk if exists
        self.load_from_disk()

        # Clean up old timestamps on startup
        self.cleanup_old_timestamps()

        self._initialized = True

    def get_timestamp(self, cliphist_id: str) -> Optional[datetime]:
        """Get timestamp for a cliphist ID.

        Args:
            cliphist_id: The cliphist ID

        Returns:
            Timestamp if found, None otherwise
        """
        with self._lock:
            return self.timestamps.get(cliphist_id)

    def update_timestamp(self, cliphist_id: str) -> None:
        """Update/add timestamp for a cliphist ID.

        Args:
            cliphist_id: The cliphist ID
        """
        with self._lock:
            self.timestamps[cliphist_id] = datetime.now()
            self.save_to_disk()

    def load_from_disk(self) -> None:
        """Load timestamps from JSON file."""
        try:
            with open(self.persist_path, "r") as f:
                data = json.load(f)
                # Convert ISO strings back to datetime objects
                self.timestamps = {
                    k: datetime.fromisoformat(v) for k, v in data.items()
                }
        except (FileNotFoundError, json.JSONDecodeError):
            # File doesn't exist or is corrupted, start fresh
            self.timestamps = {}

    def save_to_disk(self) -> None:
        """Save timestamps to JSON file."""
        try:
            # Convert datetime objects to ISO strings for JSON serialization
            data = {k: v.isoformat() for k, v in self.timestamps.items()}
            with open(self.persist_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            # Ignore write errors
            pass

    def cleanup_old_timestamps(self) -> None:
        """Remove timestamps older than max_age_days."""
        cutoff = datetime.now() - timedelta(days=self.max_age_days)
        with self._lock:
            old_count = len(self.timestamps)
            self.timestamps = {k: v for k, v in self.timestamps.items() if v > cutoff}
            new_count = len(self.timestamps)
            if old_count != new_count:
                self.save_to_disk()


class ClipboardHook(LauncherHook):
    def __init__(self, clipboard_launcher):
        self.clipboard_launcher = clipboard_launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """Handle clipboard item selection."""
        if isinstance(item_data, dict) and item_data.get("type") == "clipboard_item":
            cliphist_id = item_data.get("id")
            if cliphist_id:
                success = self.clipboard_launcher.copy_item_to_clipboard(cliphist_id)
                if success:
                    launcher.hide()
                    return True
        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle enter key for clipboard launcher."""
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle tab completion for clipboard launcher."""
        if text.startswith(">clipboard"):
            return ">clipboard "
        elif text.startswith(">cb"):
            return ">cb "
        elif text.startswith("cb:"):
            return "cb: "
        return None


class ClipboardLauncher(LauncherInterface):
    @classmethod
    def check_dependencies(cls) -> tuple[bool, str]:
        """Check if required dependencies are available.

        Returns:
            Tuple of (available, error_message)
        """
        from utils import check_cliphist, check_wl_paste

        if not check_cliphist():
            return (
                False,
                "cliphist not found. Install from https://github.com/sentriz/cliphist",
            )
        if not check_wl_paste():
            return False, "wl-paste not found. Install wl-clipboard"
        return True, ""

    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.hook = ClipboardHook(self)
        self.history_store = ClipboardHistoryStore()

        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, "hook_registry"):
            main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self) -> List[str]:
        return ["clipboard", "cb"]

    @property
    def name(self) -> str:
        return "clipboard"

    def get_size_mode(self) -> Tuple[LauncherSizeMode, Optional[Tuple[int, int]]]:
        return (LauncherSizeMode.DEFAULT, None)

    def populate(self, query: str, launcher_core) -> None:
        """Populate clipboard history items."""
        try:
            # Get clipboard history from cliphist
            cmd = ["cliphist", "list"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode != 0:
                launcher_core.add_launcher_result(
                    "Error: Could not access clipboard history",
                    "Check if cliphist is running",
                )
                return

            lines = result.stdout.strip().splitlines()
            if not lines:
                launcher_core.add_launcher_result(
                    "No clipboard history found", "Copy some text to see it here"
                )
                return

            # Filter by query if provided
            if query.strip():
                query_lower = query.lower()
                filtered_lines = []
                for line in lines:
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        _, preview = parts
                        if query_lower in preview.lower():
                            filtered_lines.append(line)
                lines = filtered_lines[:30]  # Limit to 30 results
            else:
                lines = lines[:30]  # Limit to 30 results

            # Process items
            items_added = 0

            for line in lines:
                if not line.strip():
                    continue

                # Parse cliphist output: "id\tpreview"
                parts = line.split("\t", 1)
                if len(parts) != 2:
                    continue

                cliphist_id, preview = parts

                # Get or create timestamp
                timestamp = self.history_store.get_timestamp(cliphist_id)
                if timestamp is None:
                    # New item, add current timestamp
                    self.history_store.update_timestamp(cliphist_id)
                    timestamp = self.history_store.get_timestamp(cliphist_id)

                # Format timestamp for display
                timestamp_str = (
                    self._format_timestamp(timestamp) if timestamp else "Unknown"
                )

                # Create display text (truncated preview)
                display_text = preview[:100]  # cliphist already limits to 100 chars

                # Add result
                item_data = {
                    "type": "clipboard_item",
                    "id": cliphist_id,
                    "preview": preview,
                }

                launcher_core.add_launcher_result(
                    display_text,
                    timestamp_str,
                    index=items_added + 1,
                    action_data=item_data,
                    icon_name="edit-paste",
                )

                items_added += 1

        except subprocess.TimeoutExpired:
            launcher_core.add_launcher_result(
                "Timeout: Could not access clipboard history",
                "cliphist may be unresponsive",
            )
        except Exception as e:
            launcher_core.add_launcher_result("Error loading clipboard history", str(e))

        # Scroll to top (optional, for real launcher cores)
        try:
            vadj = launcher_core.scrolled.get_vadjustment()
            if vadj:
                vadj.set_value(0)
        except AttributeError:
            pass  # Not available in test/mock environments
        launcher_core.current_apps = []

    def copy_item_to_clipboard(self, cliphist_id: str) -> bool:
        """Copy a cliphist item to the clipboard.

        Args:
            cliphist_id: The cliphist ID to copy

        Returns:
            True if successful, False otherwise
        """
        try:
            # Decode and copy the item using cliphist
            cmd = ["cliphist", "decode", cliphist_id]
            decode_result = subprocess.run(cmd, capture_output=True, timeout=5)

            if decode_result.returncode != 0:
                return False

            # Copy to clipboard using wl-copy
            copy_cmd = ["wl-copy"]
            copy_result = subprocess.run(
                copy_cmd, input=decode_result.stdout, timeout=5
            )

            return copy_result.returncode == 0

        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False

    def _format_timestamp(self, timestamp: datetime) -> str:
        """Format a timestamp for display.

        Args:
            timestamp: The timestamp to format

        Returns:
            Formatted timestamp string
        """
        now = datetime.now()
        diff = now - timestamp

        if diff.total_seconds() < 60:
            return "Just now"
        elif diff.total_seconds() < 3600:  # Less than 1 hour
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif diff.total_seconds() < 86400:  # Less than 1 day
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.days == 1:
            return "Yesterday"
        elif diff.days < 7:
            return f"{diff.days} days ago"
        else:
            # For older items, show date
            return timestamp.strftime("%b %d, %Y")
