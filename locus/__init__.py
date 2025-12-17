"""
Locus - A GTK4-based application launcher with status bar.

A modular launcher system with support for:
- Application launching
- Calculator functionality
- Bluetooth device management
- Wallpaper management
- Timer functionality
- Process management
- Bookmarks
- System monitoring
"""

__version__ = "0.1.0"
__author__ = "Locus Team"
__description__ = "A GTK4-based application launcher with status bar"

from core.launcher import Launcher
from core.status_bar import StatusBar
from core.hooks import LauncherHook, HookRegistry

__all__ = [
    "Launcher",
    "StatusBar",
    "LauncherHook",
    "HookRegistry",
]
