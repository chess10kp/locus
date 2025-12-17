"""Launcher modules for different functionality."""

from .calc_launcher import CalcLauncher, CalcHook
from .bookmark_launcher import BookmarkLauncher, BookmarkHook
from .bluetooth_launcher import BluetoothLauncher, BluetoothHook
from .monitor_launcher import MonitorLauncher, MonitorHook
from .wallpaper_launcher import WallpaperLauncher, WallpaperHook
from .timer_launcher import TimerLauncher, TimerHook
from .kill_launcher import KillLauncher, KillHook
from .music_launcher import MusicLauncher, MusicHook

__all__ = [
    "CalcLauncher",
    "CalcHook",
    "BookmarkLauncher",
    "BookmarkHook",
    "BluetoothLauncher",
    "BluetoothHook",
    "MonitorLauncher",
    "MonitorHook",
    "WallpaperLauncher",
    "WallpaperHook",
    "TimerLauncher",
    "TimerHook",
    "KillLauncher",
    "KillHook",
    "MusicLauncher",
    "MusicHook",
]
