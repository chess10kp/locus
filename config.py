CITY: str = "detroit"
APPNAME = "locus_bar"

# Custom launchers configuration
# Each launcher can be:
# - str: app name to launch
# - dict: with 'type' key
#   - 'app': launch desktop app by name
#   - 'command': run shell command
#   - 'url': open URL in browser
#   - 'builtin': special built-in functionality
CUSTOM_LAUNCHERS = {
    "editor": "Emacs",
    "calc": {"type": "builtin", "handler": "calculator"},
    "bookmark": {"type": "builtin", "handler": "bookmark"},
    "bluetooth": {"type": "builtin", "handler": "bluetooth"},
    "shutdown": {"type": "command", "cmd": "systemctl poweroff"},
    "reboot": {"type": "command", "cmd": "systemctl reboot"},
    "suspend": {"type": "command", "cmd": "systemctl suspend"},
    "hibernate": {"type": "command", "cmd": "systemctl hibernate"},
    "logout": {"type": "command", "cmd": "kill -9 -1"},
    "lock": {"type": "command", "cmd": "betterlockscreen -l || i3lock || swaylock"},
}


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
    """
    CUSTOM_LAUNCHERS[name] = launcher


def remove_custom_launcher(name: str):
    """Remove a custom launcher."""
    CUSTOM_LAUNCHERS.pop(name, None)
