import subprocess

import os

APPNAME = "locus_bar"

# Paths
MUSIC_DIR = os.path.expanduser("~/Music")
WALLPAPER_DIR = os.path.expanduser("~/Pictures/wp/")
SOCKET_PATH = "/tmp/locus_socket"

# LOCK CONFIG
# TODO: get the user's sudo pass for the lock screen'
LOCK_PASSWORD = "admin"  # Default password

# Each command can be:
# - str: A simple shell command
# - list: A command with arguments (e.g., ["notify-send", "Focus started"])
FOCUS_MODE_HOOKS = {
    "on_start": [
        ["scrollmsg", "mode", "focus"],
        ["emacsclient", "-e", "-u", "(let ((inhibit-message t)) (org-clock-in-last))"],
    ],
    "on_stop": [
        ["scrollmsg", "mode", "default"],
        ["emacsclient", "-e", "-u", "(let ((inhibit-message t)) (org-clock-out) )"],
    ],
}


NOTIFICATION_CONFIG = {
    "history": {
        "max_history": 500,
        "max_age_days": 30,
        "persist_path": "~/.cache/locus/notification_history.json",
    },
    "ui": {
        "icon": "󰂚",
        "show_unread_count": True,
        "max_display": 50,
        "group_by_app": True,
        "timestamp_format": "%H:%M",
    },
    "daemon": {
        "use_external": False,
        "external_command": "notify-send",
        "intercept_dbus": False,
    },
}

NOTIFICATION_DAEMON_CONFIG = {
    "enabled": True,
    "position": "top-right",
    "max_banners": 5,
    "banner_gap": 10,
    "banner_width": 400,
    "banner_height": 100,
    "animation_duration": 200,
    "timeouts": {
        "low": 3000,
        "normal": 5000,
        "critical": -1,
    },
    "colors": {
        "low": "#89b4fa",
        "normal": "#cba6f7",
        "critical": "#f38ba8",
    },
}

LAUNCHER_CONFIG = {
    # Display and Window Settings
    "window": {
        "width": 600,
        "height": 400,
        "default_width": 600,
        "default_height": 400,
        "wallpaper_width": 1000,
        "wallpaper_height": 600,
        "resizable": True,
        "modal": False,
        "always_on_top": False,
        "decorated": False,
        "show_menubar": False,
        "destroy_with_parent": True,
        "hide_on_close": True,
    },
    # Animation Settings
    "animation": {
        "enable_slide_in": True,
        "slide_duration": 20,  # milliseconds per frame
        "slide_step": 100,  # pixels per frame
        "target_margin": 20,  # Target margin from top edge (20px statusbar + 20px padding)
    },
    # Search and Filtering
    "search": {
        "max_results": 20,  # Maximum number of search results to show
        "max_command_results": 10,  # Max results for command mode
        "debounce_delay": 150,  # milliseconds to wait before searching
        "fuzzy_search": False,  # Enable fuzzy matching (not implemented yet)
        "case_sensitive": False,
        "search_in_exec": False,  # Search in executable names, not just display names
        "show_hidden_apps": False,  # Show NoDisplay=true apps
    },
    # Performance and Caching
    "performance": {
        "enable_cache": True,
        "cache_max_age_hours": 24,  # How long to consider cache valid
        "search_cache_size": 100,  # Max number of search results to cache
        "enable_background_loading": True,
        "enable_parallel_scanning": False,  # Disable parallel scanning to avoid GTK memory corruption
        "button_pool_enabled": True,  # Reuse buttons instead of creating new ones
        "lazy_load_apps": True,  # Only load apps when launcher is first opened
        "max_visible_results": 12,  # Maximum number of results to show (for performance)
        "batch_ui_updates": True,  # Batch UI updates to reduce GTK calls
    },
    # UI Appearance
    "ui": {
        "placeholder_text": "Search applications...",
        "show_loading_indicator": True,
        "loading_text": "Loading applications...",
        "show_keyboard_hints": True,  # Show Alt+1-9 hints
        "clear_input_on_hide": False,  # Clear search input when hiding (must be False for resume)
        "auto_grab_focus": True,  # Auto-focus search entry when shown
        "resume_last_session": True,  # Resume launcher with previous state
    },
    # Icon Configuration
    "icons": {
        "enable_icons": True,  # Master toggle for icons in search results
        "icon_size": 32,  # Icon size in pixels (default 32px)
        "cache_icons": True,  # Cache loaded icons for performance
        "cache_size": 200,  # Maximum number of icons to keep in memory cache
        "fallback_icon": "image-missing",  # Fallback icon when icon fails to load
        "use_file_type_icons": True,  # Use file type icons for files
        "async_loading": True,  # Load icons asynchronously for better performance
    },
    # Frecency Configuration
    "frecency": {
        "enabled": True,
        "recency_multipliers": {
            "hour": 4.0,  # < 1 hour ago
            "day": 2.0,  # < 24 hours ago
            "week": 1.0,  # < 7 days ago
            "older": 0.5,  # > 7 days ago
        },
        "boost_factor": 0.3,  # Frecency boost factor (0-1)
        "max_history_items": 500,  # Maximum items to track
        "prune_age_days": 90,  # Prune items older than this
    },
    # Behavior
    "behavior": {
        "activate_on_hover": False,  # Activate items on hover (not implemented)
        "clear_search_on_activate": True,  # Clear search after launching
        "close_on_activate": True,  # Close launcher after launching
        "show_recent_apps": False,  # Show recently used apps (not implemented)
        "max_recent_apps": 5,  # Number of recent apps to show
        "desktop_launcher_fast_path": True,  # Skip hooks for desktop launcher mode (direct app launch)
    },
    # Keyboard Shortcuts
    "keys": {
        "up": ["Up", "Ctrl+P", "Ctrl+K"],  # Navigate up
        "down": ["Down", "Ctrl+N", "Ctrl+J"],  # Navigate down
        "activate": ["Return", "KP_Enter"],  # Activate selected item
        "close": ["Escape"],  # Close launcher
        "tab_complete": ["Tab", "Ctrl+L"],  # Tab completion
        "quick_select": [
            "Alt+1",
            "Alt+2",
            "Alt+3",
            "Alt+4",
            "Alt+5",
            "Alt+6",
            "Alt+7",
            "Alt+8",
            "Alt+9",
        ],
    },
    # Desktop Application Loading
    "desktop_apps": {
        "scan_user_dir": True,  # Scan ~/.local/share/applications
        "scan_system_dirs": True,  # Scan /usr/share/applications
        "scan_flatpak": False,  # Scan Flatpak exports (disabled by default for speed)
        "scan_snap": False,  # Scan snap applications (disabled by default for speed)
        "scan_opt_dirs": False,  # Scan /opt applications (disabled by default for speed)
        "custom_dirs": [],  # Additional directories to scan
        "max_scan_time": 5.0,  # Maximum time in seconds to spend scanning
    },
    # Cache File Locations
    "cache": {
        "cache_dir": "~/.cache/locus",
        "apps_cache_file": "desktop_apps.json",
        "search_cache_file": "search_cache.json",  # Not implemented yet
    },
    # Advanced Options
    "advanced": {
        "debug_print": False,  # Print debug information to console
        "profile_loading": False,  # Profile app loading time
        "validate_desktop_files": True,  # Validate .desktop file format
        "sort_apps_alphabetically": True,  # Sort apps by name
        "deduplicate_apps": True,  # Remove duplicate app entries
    },
}


def todo_capture():
    """Open Emacs org-capture for todo."""
    # Check if emacs daemon is running
    result = subprocess.run(["pgrep", "-f", "emacs --daemon"], capture_output=True)
    if result.returncode != 0:
        return
    # Open org-capture with todo template
    subprocess.Popen(["emacsclient", "-c", "-e", '(org-capture nil "t")'])


# Bar Layout Configuration
# Available modules:
# - launcher: Application launcher button
# - workspaces: Workspace indicators
# - binding_mode: Current Sway binding mode
# - emacs_clock: Emacs org-mode clock
# - time: Current time
# - battery: Battery status
# - custom_message: Custom status messages via IPC
BAR_LAYOUT = {
    "left": ["launcher", "workspaces", "binding_mode", "emacs_clock"],
    "middle": [],
    "right": ["notifications", "time", "battery", "custom_message"],
}

# Module Configuration Options
# Each module can have its own configuration options
MODULE_CONFIG = {
    "time": {
        "format": "%H:%M",  # Time format string
        "interval": 60,  # Update interval in seconds
    },
    "battery": {
        "interval": 60,  # Update interval in seconds
        "show_percentage": True,  # Show percentage in addition to icon
    },
    "workspaces": {
        "show_labels": True,  # Show workspace labels
        "highlight_focused": True,  # Highlight focused workspace
    },
    "binding_mode": {
        "interval": 1,  # Update interval in seconds
    },
    "emacs_clock": {
        "interval": 10,  # Update interval in seconds
        "fallback_text": "Not (c)locked in",  # Text when no clock active
    },
    "launcher": {
        # No configuration needed for static module
    },
    "custom_message": {
        # No configuration needed for on-demand module
    },
}


CLIPBOARD_CONFIG = {
    "history": {
        "max_history": 30,  # Show 30 entries
        "max_age_days": 30,  # Keep timestamps for 30 days
        "timestamp_cache": "~/.cache/locus/clipboard_timestamps.json",
    },
    "ui": {
        "preview_length": 100,  # Characters to show (from cliphist)
        "timestamp_format": "relative",  # "relative" or "absolute"
    },
}


# Custom launchers configuration
# Each launcher can be:
# - str: app name to launch
# - dict: with 'type' key
#   - 'app': launch desktop app by name
#   - 'command': run shell command
#   - 'url': open URL in browser
#   - 'builtin': special built-in functionality
#   - 'function': call a Python function (func key)
# Plugin authors can update the status bar by calling utils.send_status_message(message)
# Metadata for launcher entries
# Keyed by entry identifier (usually the display name or command)
METADATA = {}


CUSTOM_LAUNCHERS = {
    "calc": {"type": "builtin", "handler": "calculator"},
    "bookmark": {"type": "builtin", "handler": "bookmark"},
    "bluetooth": {"type": "builtin", "handler": "bluetooth"},
    "wifi": {"type": "builtin", "handler": "wifi"},
    "wallpaper": {"type": "builtin", "handler": "wallpaper"},
    "timer": {"type": "builtin", "handler": "timer"},
    "web": {"type": "builtin", "handler": "web"},
    "clipboard": {"type": "builtin", "handler": "clipboard"},
    "todo": {"type": "function", "func": todo_capture},  # doesn't work for now
    "shutdown": {"type": "command", "cmd": "systemctl poweroff"},
    "reboot": {"type": "command", "cmd": "systemctl reboot"},
    "suspend": {"type": "command", "cmd": "systemctl suspend"},
    "hibernate": {"type": "command", "cmd": "systemctl hibernate"},
    "logout": {"type": "command", "cmd": "kill -9 -1"},
    "lock": {"type": "builtin", "handler": "lock"},
    "music": {"type": "builtin", "handler": "music"},
    "refile": {"type": "builtin", "handler": "refile"},
    "ai": {"type": "builtin", "handler": "llm_chat"},
}

# =================================
# WEB SEARCH CONFIGURATION
# =================================

# Search engine presets
SEARCH_ENGINES = {
    "gg": "https://www.google.com/search?q={}",
    "sp": "https://www.startpage.com/sp/search?query={}",
    "bs": "https://search.brave.com/search?q={}",
    "dg": "https://duckduckgo.com/?q={}",
    "bg": "https://www.bing.com/search?q={}",
    "ec": "https://www.ecosia.org/search?q={}",
}

# Default search engine (must be a key from SEARCH_ENGINES)
DEFAULT_SEARCH_ENGINE = "gg"

# Command to open URLs (use None to let xdg-open decide)
# Examples:
#   - None: use xdg-open (system default)
#   - "firefox": open in Firefox
#   - "chromium": open in Chromium
#   - "google-chrome": open in Google Chrome
URL_OPENER = None  # None means use xdg-open

# Custom launchers configuration
METADATA.update(
    {
        "calc": "Calculator",
        "bookmark": "Bookmarks",
        "bluetooth": "Bluetooth",
        "brightness": "Brightness control",
        "wifi": "WiFi manager",
        "wallpaper": "Wallpaper",
        "timer": "Timer",
        "clipboard": "Clipboard History",
        "todo": "Todo capture",
        "shutdown": "Shutdown",
        "reboot": "Reboot",
        "suspend": "Suspend",
        "hibernate": "Hibernate",
        "logout": "Logout",
        "lock": "Lock screen",
        "mpd": "MPD client",
        "refile": "Sway Workspace swapper",
        "web": "Web search",
        "file": "File search",
        "f": "File search",
    }
)


def add_custom_launcher(name: str, launcher):
    """Add a custom launcher.

    Args:
        name: The command name (e.g., 'myapp')
        launcher: Either a string (app name) or dict with type info

    Examples:
        add_custom_launcher("google", {"type": "url", "url": "https://google.com"})
    """
    CUSTOM_LAUNCHERS[name] = launcher


def add_function_launcher(name: str, func):
    """Add a launcher that calls a Python function.

    Args:
        name: The command name
        func: A callable Python function

    The function can update the status bar by calling utils.send_status_message(message)
    """
    CUSTOM_LAUNCHERS[name] = {"type": "function", "func": func}


def remove_custom_launcher(name: str):
    """Remove a custom launcher."""
    CUSTOM_LAUNCHERS.pop(name, None)


def add_metadata(identifier: str, metadata: str):
    """Add metadata for a launcher entry.

    Args:
        identifier: The entry identifier (usually the display name or command)
        metadata: The metadata string to display

    Examples:
        add_metadata("Firefox", "Web Browser")
        add_metadata("calc", "Calculator mode")
    """
    METADATA[identifier] = metadata


# Define custom prefixes for launchers to override default triggers.
# Format: {launcher_name: [prefix1, prefix2, ...]}
#
# Prefix styles supported:
#   - Colon suffix: "f:" matches "f: query"
#   - Space separator: "f" matches "f query" (f followed by space)
#   - With > prefix: ">file" (traditional, but not recommended here)
#
# If a launcher is listed here, ONLY these triggers are used.
# If not listed, the launcher's default triggers are used.
#
# Examples:
#   LAUNCHER_PREFIXES = {
#       "file": ["f:"],        # Use "f:" instead of ">file"
#       "wallpaper": ["wp:"],   # Use "wp:" instead of ">wallpaper"
#       "music": ["m:"],        # Use "m:" instead of ">music"
#       "wifi": ["w:"],         # Use "w:" instead of ">wifi"
#       "bluetooth": ["bt:"],   # Use "bt:" instead of ">bluetooth"
#       "calc": ["c:"],         # Use "c:" instead of ">calc"
#       "emoji": ["e:"],        # Use "e:" instead of ">emoji"
#   }
#
# Available launcher names:
#   file, wallpaper, music, wifi, bluetooth, calc, bookmark,
#   timer, web, emoji, gallery, kill, shell, refile, focus, lock

# Volume and Brightness Commands
# These are the shell commands used for adjusting and getting volume/brightness
# Users can modify these strings to use different tools or step sizes
VOL_UP_CMD = "pamixer --increase 5"
VOL_DOWN_CMD = "pamixer --decrease 5"
VOL_GET_CMD = "pamixer --get-volume"
VOL_MUTE_CMD = "pamixer --toggle-mute"

BRIGHT_UP_CMD = "brightnessctl set +5%"
BRIGHT_DOWN_CMD = "brightnessctl set 5%-"
BRIGHT_GET_CMD = "echo $(( $(brightnessctl get) * 100 / $(brightnessctl max) ))"

LAUNCHER_PREFIXES = {
    # Example custom prefixes - feel free to modify
    "file": ["f:"],  # Type "f:" instead of ">file"
    "wallpaper": ["wp:"],  # Type "wp:" instead of ">wallpaper"
    "mpd": ["m"],  # Type "m " instead of ">music"
    "wifi": ["w"],  # Type "w " instead of ">wifi"
}

LAUNCHER_PREFIX_SHORTCUTS = {
    # Key bindings to automatically type launcher prefixes
    # These work even when text is already in the search entry
    "Ctrl+F": "file",  # Types "f: " (using custom prefix)
    "Ctrl+W": "wallpaper",  # Types "wp: " (using custom prefix)
}


def remove_metadata(identifier: str):
    """Remove metadata for a launcher entry."""
    METADATA.pop(identifier, None)
