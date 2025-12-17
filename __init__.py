__version__ = "0.1.0"
__author__ = "Nitin Madhu"
__description__ = "A GTK4-based application launcher with status bar"

from .core.launcher import Launcher
from .core.status_bar import StatusBar
from .core.hooks import LauncherHook, HookRegistry

__all__ = [
    "Launcher",
    "StatusBar",
    "LauncherHook",
    "HookRegistry",
]
