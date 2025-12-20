from typing import Optional, Any, Dict
from enum import Enum


class ResultType(Enum):
    """Types of search results."""

    APP = "app"
    COMMAND = "command"
    LAUNCHER = "launcher"
    LOADING = "loading"
    CUSTOM = "custom"


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


class AppSearchResult(SearchResult):
    """Search result for applications."""

    def __init__(self, app: Dict[str, Any], index: int = 0):
        title = app.get("name", "")
        subtitle = app.get("description", "")
        super().__init__(title, subtitle, ResultType.APP)
        self.app = app
        self.index = index
        self.action_data = app


class CommandSearchResult(SearchResult):
    """Search result for shell commands."""

    def __init__(self, command: str, index: int = 0):
        super().__init__(f"Run: {command}", "", ResultType.COMMAND)
        self.command = command
        self.index = index
        self.action_data = command


class LauncherSearchResult(SearchResult):
    """Search result for registered launchers."""

    def __init__(self, command: str, metadata: str = "", index: int = 0):
        super().__init__(f">{command}", metadata, ResultType.LAUNCHER)
        self.command = command
        self.index = index
        self.action_data = command


class CustomSearchResult(SearchResult):
    """Search result for custom handlers."""

    def __init__(self, title: str, hook_data: Any = None, index: int = 0):
        super().__init__(title, "", ResultType.CUSTOM)
        self.hook_data = hook_data
        self.index = index
        self.action_data = hook_data


class LoadingSearchResult(SearchResult):
    """Search result for loading indicator."""

    def __init__(self, text: str = "Loading..."):
        super().__init__(text, "", ResultType.LOADING)
        self.index = None  # Loading indicators shouldn't have Alt+number hints
