"""Launcher modules for different functionality."""

# Import all launchers to trigger their auto-registration
from .calc_launcher import CalcLauncher, CalcHook
from .bookmark_launcher import BookmarkLauncher, BookmarkHook
from .bluetooth_launcher import BluetoothLauncher, BluetoothHook
from .monitor_launcher import MonitorLauncher, MonitorHook
from .wallpaper_launcher import WallpaperLauncher, WallpaperHook
from .timer_launcher import TimerLauncher, TimerHook
from .kill_launcher import KillLauncher, KillHook
from .music_launcher import MusicLauncher, MusicHook
from .refile_launcher import RefileLauncher, RefileHook

# Auto-instantiate launchers that don't require main launcher reference
# Note: Launchers that need the main launcher reference will be instantiated
# in the main launcher's _register_launchers method

def auto_register_launchers():
    """Auto-register all launcher instances."""
    # Instantiate launchers that don't require main launcher reference
    try:
        CalcLauncher()
        BookmarkLauncher()
        BluetoothLauncher()
        TimerLauncher()
        WallpaperLauncher()

        # These may need additional dependencies or configuration
        # MonitorLauncher()
        # KillLauncher()
        # MusicLauncher()
        # RefileLauncher()

    except Exception as e:
        print(f"Warning: Could not auto-register some launchers: {e}")

# Auto-register launchers when the package is imported
auto_register_launchers()

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
    "RefileLauncher",
    "RefileHook",
    "auto_register_launchers",
]
