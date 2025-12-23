# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import os
import random
from typing import List, Dict, Any, Optional
from pathlib import Path

from core.launcher_registry import LauncherInterface, LauncherSizeMode
from utils.app_loader import get_app_loader


class GalleryLauncher(LauncherInterface):
    """Example grid launcher for displaying image galleries."""

    def __init__(self, launcher_instance):
        self.launcher_instance = launcher_instance
        self._app_loader = get_app_loader()

    @property
    def command_triggers(self) -> List[str]:
        return [">gallery", ">images"]

    @property
    def name(self) -> str:
        return "gallery"

    def get_size_mode(self) -> tuple[LauncherSizeMode, Optional[tuple[int, int]]]:
        return LauncherSizeMode.GRID, (1200, 800)

    def get_grid_config(self) -> Dict[str, Any]:
        return {
            "columns": 4,
            "item_width": 250,
            "item_height": 200,
            "spacing": 10,
            "show_metadata": True,
            "metadata_position": "bottom",
            "aspect_ratio": "original",
        }

    def populate(self, query: str, launcher_core) -> None:
        """Populate gallery with sample images or search results."""

        # Sample data for demonstration - in a real launcher, this would
        # search for actual image files or fetch from an API
        sample_images = [
            {
                "title": "Sunset Photo",
                "path": "/usr/share/pixmaps/ubuntu-logo-icon.png",  # System icon as fallback
                "metadata": {"size": "2.1MB", "date": "2024-01-15", "type": "JPEG"},
            },
            {
                "title": "Mountain Landscape",
                "path": "/usr/share/pixmaps/ubuntu-logo-icon.png",  # System icon as fallback
                "metadata": {"size": "3.5MB", "date": "2024-01-14", "type": "PNG"},
            },
            {
                "title": "City Lights",
                "path": "/usr/share/pixmaps/ubuntu-logo-icon.png",  # System icon as fallback
                "metadata": {"size": "1.8MB", "date": "2024-01-13", "type": "JPEG"},
            },
            {
                "title": "Forest Path",
                "path": "/usr/share/pixmaps/ubuntu-logo-icon.png",  # System icon as fallback
                "metadata": {"size": "2.7MB", "date": "2024-01-12", "type": "PNG"},
            },
            {
                "title": "Ocean Waves",
                "path": "/usr/share/pixmaps/ubuntu-logo-icon.png",  # System icon as fallback
                "metadata": {"size": "4.2MB", "date": "2024-01-11", "type": "JPEG"},
            },
            {
                "title": "Desert Dunes",
                "path": "/usr/share/pixmaps/ubuntu-logo-icon.png",  # System icon as fallback
                "metadata": {"size": "3.1MB", "date": "2024-01-10", "type": "PNG"},
            },
            {
                "title": "Snowy Mountains",
                "path": "/usr/share/pixmaps/ubuntu-logo-icon.png",  # System icon as fallback
                "metadata": {"size": "2.9MB", "date": "2024-01-09", "type": "JPEG"},
            },
            {
                "title": "Beach Paradise",
                "path": "/usr/share/pixmaps/ubuntu-logo-icon.png",  # System icon as fallback
                "metadata": {"size": "3.8MB", "date": "2024-01-08", "type": "PNG"},
            },
        ]

        # Filter based on query if provided
        if query:
            filtered_images = [
                img for img in sample_images if query.lower() in img["title"].lower()
            ]
        else:
            filtered_images = sample_images

        # Limit to 12 items for performance (3 rows x 4 columns)
        limited_images = filtered_images[:12]

        # Add grid results
        for i, img in enumerate(limited_images):
            launcher_core.add_grid_result(
                title=img["title"],
                image_path=img["path"],
                metadata=img["metadata"],
                index=i + 1 if i < 9 else None,  # Alt+1-9 shortcuts
            )

        # If no results, show a message
        if not limited_images:
            launcher_core.add_grid_result(
                title="No images found",
                metadata={"error": "Try a different search term"},
            )

    def cleanup(self) -> None:
        """Clean up resources when launcher is unregistered."""
        pass
