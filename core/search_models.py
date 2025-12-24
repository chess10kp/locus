import logging
from typing import Optional, Any, Dict
from enum import Enum

logger = logging.getLogger("SearchModels")


class ResultType(Enum):
    """Types of search results."""

    APP = "app"
    COMMAND = "command"
    LAUNCHER = "launcher"
    LOADING = "loading"
    CUSTOM = "custom"
    WALLPAPER = "wallpaper"  # Wallpaper with image data
    GRID = "grid"  # Grid items with configurable metadata


class SearchResult:
    """Base class for search results."""

    def __init__(
        self, title: str, subtitle: str = "", result_type: ResultType = ResultType.APP
    ):
        self.title = title
        self.subtitle = subtitle
        self.result_type = result_type
        self.index = 0  # For Alt+number navigation
        self.hook_data = None  # For custom hook handling
        self.action_data = None  # Data needed to execute the action
        self.icon_name = None  # Icon name or file path
        self.icon_pixbuf = None  # Loaded GdkPixbuf (cached by icon manager)


class AppSearchResult(SearchResult):
    """Search result for applications."""

    def __init__(self, app: Dict[str, Any], index: int = 0):
        title = app.get("name", "")
        subtitle = app.get("description", "")
        super().__init__(title, subtitle, ResultType.APP)
        self.app = app
        self.index = index
        self.action_data = app
        self.icon_name = app.get("icon", None)  # Icon name or file path
        self.icon_pixbuf = None  # Loaded GdkPixbuf (cached by icon manager)

        if self.icon_name:
            try:
                from utils.icon_manager import icon_manager

                self.icon_pixbuf = icon_manager.get_icon(self.icon_name)
            except Exception as e:
                logger.warning(f"Failed to load icon for '{title}': {e}")
                self.icon_pixbuf = None


class CommandSearchResult(SearchResult):
    """Search result for shell commands."""

    def __init__(self, command: str, index: int = 0):
        super().__init__(f"Run: {command}", "", ResultType.COMMAND)
        self.command = command
        self.index = index
        self.action_data = command
        self.icon_name = "/usr/share/icons/AdwaitaLegacy/32x32/legacy/utilities-terminal.png"  # Default terminal icon
        self.icon_pixbuf = None  # Loaded GdkPixbuf (cached by icon manager)


class LauncherSearchResult(SearchResult):
    """Search result for registered launchers."""

    def __init__(
        self,
        command: str,
        metadata: str = "",
        index: int = 0,
        action_data=None,
        prefix: bool = True,
        icon_name: Optional[str] = None,
    ):
        title = f">{command}" if prefix else command
        super().__init__(title, metadata, ResultType.LAUNCHER)
        self.command = command
        self.index = index
        # Only set action_data to command if not explicitly provided
        if action_data is not None:
            self.action_data = action_data
        else:
            self.action_data = command
        self.icon_name = icon_name
        self.icon_pixbuf = None  # Loaded GdkPixbuf (cached by icon manager)

        if self.icon_name:
            try:
                from utils.icon_manager import icon_manager

                self.icon_pixbuf = icon_manager.get_icon(self.icon_name)
            except Exception as e:
                logger.warning(f"Failed to load icon for launcher '{title}': {e}")
                self.icon_pixbuf = None


class CustomSearchResult(SearchResult):
    """Search result for custom handlers."""

    def __init__(
        self,
        title: str,
        hook_data: Any = None,
        index: int = 0,
        icon_name: Optional[str] = None,
    ):
        super().__init__(title, "", ResultType.CUSTOM)
        self.hook_data = hook_data
        self.index = index
        self.action_data = hook_data
        self.icon_name = icon_name  # Optional icon for custom results
        self.icon_pixbuf = None  # Loaded GdkPixbuf (cached by icon manager)


class LoadingSearchResult(SearchResult):
    """Search result for loading indicator."""

    def __init__(self, text: str = "Loading..."):
        super().__init__(text, "", ResultType.LOADING)
        self.index = None  # Loading indicators shouldn't have Alt+number hints


class WallpaperSearchResult(SearchResult):
    """Search result for wallpaper images with thumbnails."""

    def __init__(
        self,
        title: str,
        image_path: str,
        pixbuf=None,
        index: int = 0,
        action_data=None,
    ):
        super().__init__(title, "", ResultType.WALLPAPER)
        self.image_path = image_path
        self.pixbuf = pixbuf  # GdkPixbuf for the thumbnail
        self.index = index
        self.action_data = action_data if action_data is not None else image_path
        self.icon_name = None  # Not used for wallpaper (uses image_path/pixbuf)
        self.icon_pixbuf = None  # Not used for wallpaper (uses pixbuf directly)


class GridSearchResult(SearchResult):
    """Search result for grid items with rich metadata and optional images."""

    def __init__(
        self,
        title: str,
        image_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        pixbuf=None,
        index: Optional[int] = 0,
        action_data=None,
        **kwargs,
    ):
        # Use empty subtitle by default for grid items (metadata shown differently)
        super().__init__(title, "", ResultType.GRID, **kwargs)
        self.image_path = image_path
        self.pixbuf = pixbuf  # GdkPixbuf for the thumbnail
        self.grid_metadata = metadata or {}  # Custom metadata for grid display
        self.index = index
        # Action data defaults to metadata but can be overridden
        self.action_data = action_data if action_data is not None else metadata
        self.icon_name = None  # Not used for grid (uses image_path/pixbuf)
        self.icon_pixbuf = None  # Not used for grid (uses pixbuf directly)
