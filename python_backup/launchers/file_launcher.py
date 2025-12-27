# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

"""
File search launcher with indexed file search using SQLite FTS5.
Provides fast file search with open, reveal, and copy path actions.
"""

import os
import subprocess
import logging
from typing import Tuple, Optional, List
from enum import Enum

from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from utils.file_indexer import get_file_indexer
from utils.clipboard import copy_to_clipboard

logger = logging.getLogger("FileLauncher")


class FileAction(Enum):
    """Actions available for files."""

    OPEN = "open"
    REVEAL = "reveal"
    COPY_PATH = "copy_path"


class FileHook(LauncherHook):
    """Hook for handling file actions."""

    def __init__(self, file_launcher):
        self.file_launcher = file_launcher

    def on_select(self, launcher, item_data) -> bool:
        """Handle file selection."""
        if isinstance(item_data, dict) and item_data.get("type") == "file_action":
            action = item_data.get("action")
            file_path = item_data.get("path")

            if action == FileAction.OPEN.value:
                self.file_launcher.open_file(file_path)
                launcher.hide()
            elif action == FileAction.REVEAL.value:
                self.file_launcher.reveal_file(file_path)
                launcher.hide()
            elif action == FileAction.COPY_PATH.value:
                self.file_launcher.copy_path(file_path)
                # Don't hide - allow user to see more files

            return True
        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle enter key."""
        # Use first result if available
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Tab completion for file paths."""
        # Future: Implement path completion
        return None


class FileLauncher(LauncherInterface):
    """
    File search launcher with indexed file search.

    Triggers: >file, >f
    """

    # File type icons (theme icon names for proper visual indication)
    FILE_ICONS = {
        "text/plain": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/document-new.png",
        "text/markdown": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/document-new.png",
        "text/x-python": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/accessories-text-editor.png",
        "text/javascript": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/accessories-text-editor.png",
        "text/typescript": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/accessories-text-editor.png",
        "application/json": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/document-new.png",
        "application/pdf": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/document-new.png",
        "image/png": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/insert-image.png",
        "image/jpeg": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/insert-image.png",
        "image/gif": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/insert-image.png",
        "image/svg+xml": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/insert-image.png",
        "image/webp": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/insert-image.png",
        "audio/mpeg": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/document-new.png",
        "audio/flac": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/document-new.png",
        "audio/wav": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/document-new.png",
        "video/mp4": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/document-new.png",
        "video/webm": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/document-new.png",
        "application/zip": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/document-new.png",
        "application/x-tar": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/document-new.png",
        "application/gzip": "/usr/share/icons/AdwaitaLegacy/32x32/legacy/document-new.png",
        "application/octet-stream": "application-x-executable",
    }

    def __init__(self, main_launcher=None):
        if main_launcher:
            self.hook = FileHook(self)
            main_launcher.hook_registry.register_hook(self.hook)

        self.indexer = get_file_indexer()

        # Start indexer on first use
        if not self.indexer.is_ready() and not self.indexer.running:
            logger.info("Starting file indexer...")
            self.indexer.start()

    @property
    def command_triggers(self) -> List[str]:
        return ["file", "f"]

    @property
    def name(self) -> str:
        return "file"

    def get_size_mode(self) -> Tuple[LauncherSizeMode, Optional[Tuple[int, int]]]:
        return (LauncherSizeMode.DEFAULT, None)

    def handles_tab(self) -> bool:
        return True

    def handle_tab(self, query: str, launcher_core) -> Optional[str]:
        """Handle tab completion for file paths."""
        # Future: Implement path completion
        return None

    def populate(self, query: str, launcher_core) -> None:
        """
        Populate launcher with file search results.

        Shows results within ~50ms for typical queries.
        """
        # Show indexer status if not ready
        if not self.indexer.is_ready():
            scan_info = self.indexer.get_last_scan_info()
            if scan_info["file_count"] == 0:
                launcher_core.add_launcher_result(
                    "Indexing files...",
                    "Please wait for initial scan to complete",
                    index=1,
                )
                return
            else:
                launcher_core.add_launcher_result(
                    f"Scanning... {scan_info['file_count']:,} files indexed",
                    "Search available, but index is still updating",
                    index=1,
                )

        # Show empty query help
        if not query:
            launcher_core.add_launcher_result(
                "File Search", "Type to search files (~50ms for 100k+ files)", index=1
            )

            # Show scan info
            file_count = self.indexer.get_file_count()
            launcher_core.add_launcher_result(
                f"Indexed: {file_count:,} files",
                "Home directory with smart exclusions",
                index=2,
            )
            return

        # Search files
        results = self.indexer.search_files(query, limit=50)

        if not results:
            launcher_core.add_launcher_result(
                f"No results for '{query}'",
                "Try different keywords or wait for scan to complete",
                index=1,
            )
            return

        # Display results
        index = 1
        for file_result in results:
            # Get display name (truncated if needed)
            display_name = file_result.name
            if len(display_name) > 60:
                display_name = display_name[:57] + "..."

            # Get display path (relative to home if possible)
            display_path = self._format_path(file_result.path)
            if len(display_path) > 80:
                # Show parent dir instead
                display_path = os.path.basename(file_result.parent_path) + "/"

            # Get icon for file type
            icon_name = self.FILE_ICONS.get(file_result.file_type, "text-x-generic")

            # Format size
            size_str = self._format_size(file_result.size)

            metadata = f"{size_str}"

            # Add action data
            action_data = {
                "type": "file_action",
                "action": FileAction.OPEN.value,
                "path": file_result.path,
                "file_result": file_result,
            }

            launcher_core.add_launcher_result(
                display_name,
                metadata,
                index=index if index <= 9 else None,
                action_data=action_data,
                icon_name=icon_name,
            )

            index += 1
            if index > 50:  # Limit results
                break

    def open_file(self, file_path: str) -> bool:
        """Open file with default application."""
        try:
            # Use xdg-open for cross-platform file opening
            subprocess.Popen(
                ["xdg-open", file_path],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info(f"Opened file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to open {file_path}: {e}")
            return False

    def reveal_file(self, file_path: str) -> bool:
        """Reveal file in file manager."""
        try:
            subprocess.Popen(
                ["xdg-open", os.path.dirname(file_path)],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info(f"Revealed file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to reveal {file_path}: {e}")
            return False

    def copy_path(self, file_path: str) -> bool:
        """Copy file path to clipboard."""
        try:
            success = copy_to_clipboard(file_path)
            if success:
                logger.info(f"Copied path: {file_path}")
            return success
        except Exception as e:
            logger.error(f"Failed to copy path: {e}")
            return False

    def _format_path(self, path: str) -> str:
        """Format path for display (relative to home if possible)."""
        home = os.path.expanduser("~")
        if path.startswith(home):
            return path.replace(home, "~", 1)
        return path

    def _format_size(self, size_bytes: int) -> str:
        """Format file size for display."""
        size_float = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size_float < 1024.0:
                return f"{size_float:.1f}{unit}"
            size_float /= 1024.0
        return f"{size_float:.1f}TB"

    def cleanup(self) -> None:
        """Clean up resources."""
        # Indexer continues running in background
        pass
