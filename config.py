import subprocess

CITY: str = "detroit"
APPNAME = "locus_bar"


def todo_capture():
    """Open Emacs org-capture for todo."""
    # Check if emacs daemon is running
    result = subprocess.run(["pgrep", "-f", "emacs --daemon"], capture_output=True)
    if result.returncode != 0:
        print("Emacs daemon not running")
        return
    # Open org-capture with todo template
    subprocess.Popen(["emacsclient", "-c", "-e", '(org-capture nil "t")'])


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
    "editor": "Emacs",
    "calc": {"type": "builtin", "handler": "calculator"},
    "bookmark": {"type": "builtin", "handler": "bookmark"},
    "bluetooth": {"type": "builtin", "handler": "bluetooth"},
    "wallpaper": {"type": "builtin", "handler": "wallpaper"},
    "timer": {"type": "builtin", "handler": "timer"},
    "monitor": {"type": "builtin", "handler": "monitor"},
    "todo": {"type": "function", "func": todo_capture},
    "shutdown": {"type": "command", "cmd": "systemctl poweroff"},
    "reboot": {"type": "command", "cmd": "systemctl reboot"},
    "suspend": {"type": "command", "cmd": "systemctl suspend"},
    "hibernate": {"type": "command", "cmd": "systemctl hibernate"},
    "logout": {"type": "command", "cmd": "kill -9 -1"},
    "lock": {"type": "command", "cmd": "betterlockscreen -l || i3lock || swaylock"},
}

# Add default metadata for built-in launchers
METADATA.update(
    {
        "editor": "Text editor",
        "calc": "Calculator",
        "bookmark": "Bookmarks",
        "bluetooth": "Bluetooth",
        "wallpaper": "Wallpaper",
        "timer": "Timer",
        "monitor": "Monitor control",
        "todo": "Todo capture",
        "shutdown": "Shutdown",
        "reboot": "Reboot",
        "suspend": "Suspend",
        "hibernate": "Hibernate",
        "logout": "Logout",
        "lock": "Lock screen",
    }
)


def add_custom_launcher(name: str, launcher):
    """Add a custom launcher.

    Args:
        name: The command name (e.g., 'myapp')
        launcher: Either a string (app name) or dict with type info

    Examples:
        add_custom_launcher("google", {"type": "url", "url": "https://google.com"})
        add_custom_launcher("myterm", {"type": "command", "cmd": "alacritty"})
        add_custom_launcher("vscode", {"type": "app", "name": "Visual Studio Code"})
        add_custom_launcher("calc", {"type": "builtin", "handler": "calculator"})
        add_custom_launcher("myfunc", {"type": "function", "func": my_python_function})
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


def remove_metadata(identifier: str):
    """Remove metadata for a launcher entry."""
    METADATA.pop(identifier, None)
