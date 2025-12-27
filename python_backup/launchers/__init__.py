"""Launcher modules for different functionality."""

# Import all launchers to trigger their auto-registration
from .calc_launcher import CalcLauncher, CalcHook
from .bookmark_launcher import BookmarkLauncher, BookmarkHook
from .bluetooth_launcher import BluetoothLauncher, BluetoothHook
from .wallpaper_launcher import WallpaperLauncher, WallpaperHook
from .timer_launcher import TimerLauncher, TimerHook
from .brightness_launcher import BrightnessLauncher, BrightnessHook
from .focus_launcher import FocusLauncher, FocusHook
from .kill_launcher import KillLauncher, KillHook
from .music_launcher import MpdLauncher, MpdHook
from .refile_launcher import RefileLauncher, RefileHook
from .shell_launcher import ShellLauncher, ShellHook
from .file_launcher import FileLauncher, FileHook
from .dmenu_launcher import DmenuLauncher, DmenuHook
from .color_launcher import ColorLauncher, ColorHook
from .keybinding_launcher import KeybindingLauncher, KeybindingHook
# Notification launcher disabled for now
# from .notification_launcher import NotificationLauncher, NotificationHook

# Auto-instantiate launchers that don't require main launcher reference
# Note: Launchers that need the main launcher reference will be instantiated
# in the main launcher's _register_launchers method


def auto_register_launchers():
    """Auto-register all launcher instances."""
    # All launchers now require main launcher reference, so none are auto-registered here
    # They are all instantiated in the main launcher's _register_launchers() method
    pass


# Auto-register launchers when the package is imported
auto_register_launchers()

__all__ = [
    "CalcLauncher",
    "CalcHook",
    "BookmarkLauncher",
    "BookmarkHook",
    "BluetoothLauncher",
    "BluetoothHook",
    "WallpaperLauncher",
    "WallpaperHook",
    "TimerLauncher",
    "TimerHook",
    "BrightnessLauncher",
    "BrightnessHook",
    "FocusLauncher",
    "FocusHook",
    "KillLauncher",
    "KillHook",
    "MpdLauncher",
    "MusicHook",
    "RefileLauncher",
    "RefileHook",
    "ShellLauncher",
    "ShellHook",
    "FileLauncher",
    "FileHook",
    "DmenuLauncher",
    "DmenuHook",
    "ColorLauncher",
    "ColorHook",
    "KeybindingLauncher",
    "KeybindingHook",
    # Notification launcher disabled for now
    # "NotificationLauncher",
    # "NotificationHook",
    "auto_register_launchers",
]
