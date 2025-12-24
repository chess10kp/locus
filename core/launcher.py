# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

"""
Core launcher module - main entry point for launcher functionality.

This module provides a unified interface to the launcher system by exporting
classes and functions from the refactored sub-modules.
"""

# Re-export core classes for backward compatibility
from .wrapped_result import WrappedSearchResult
from .popup import Popup
from .launcher_window import Launcher, show_lock_screen
from .process_launcher import (
    AppLauncher,
    PerformanceMonitor,
    launch_detached,
    register_builtin_handler,
    handle_custom_launcher,
    BUILTIN_HANDLERS,
)
from .launcher_ui import LauncherUI
from .launcher_search import LauncherSearch
from .launcher_navigation import LauncherNavigation
from .utils.time_parsing import parse_time

# Module-level exports for backward compatibility
__all__ = [
    "WrappedSearchResult",
    "Popup",
    "Launcher",
    "show_lock_screen",
    "AppLauncher",
    "PerformanceMonitor",
    "launch_detached",
    "register_builtin_handler",
    "handle_custom_launcher",
    "BUILTIN_HANDLERS",
    "LauncherUI",
    "LauncherSearch",
    "LauncherNavigation",
    "parse_time",
]
