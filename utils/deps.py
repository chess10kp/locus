# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import shutil
import subprocess
from typing import List, Optional


def check_command_exists(command: str) -> bool:
    """Check if a command is available on the system.

    Args:
        command: The command to check (e.g., "nmcli", "bluetoothctl")

    Returns:
        True if the command exists, False otherwise
    """
    return shutil.which(command) is not None


def check_commands_exist(commands: List[str]) -> bool:
    """Check if all commands in a list are available.

    Args:
        commands: List of commands to check

    Returns:
        True if all commands exist, False otherwise
    """
    return all(check_command_exists(cmd) for cmd in commands)


def get_missing_commands(commands: List[str]) -> List[str]:
    """Get list of missing commands from a list.

    Args:
        commands: List of commands to check

    Returns:
        List of commands that are not available
    """
    return [cmd for cmd in commands if not check_command_exists(cmd)]


def check_file_exists(path: str) -> bool:
    """Check if a file exists.

    Args:
        path: Path to the file (supports ~ expansion)

    Returns:
        True if the file exists, False otherwise
    """
    import os
    expanded = os.path.expanduser(path)
    return os.path.exists(expanded)


def check_notify_send() -> bool:
    """Check if notify-send is available.

    Returns:
        True if notify-send exists, False otherwise
    """
    return check_command_exists("notify-send")


def check_clipboard() -> bool:
    """Check if clipboard utilities are available.

    Returns:
        True if wl-copy or xclip is available, False otherwise
    """
    return check_command_exists("wl-copy") or check_command_exists("xclip")


def check_nmcli() -> bool:
    """Check if nmcli (NetworkManager) is available.

    Returns:
        True if nmcli exists, False otherwise
    """
    return check_command_exists("nmcli")


def check_bluetoothctl() -> bool:
    """Check if bluetoothctl is available.

    Returns:
        True if bluetoothctl exists, False otherwise
    """
    return check_command_exists("bluetoothctl")


def check_mpc() -> bool:
    """Check if mpc (Music Player Daemon client) is available.

    Returns:
        True if mpc exists, False otherwise
    """
    return check_command_exists("mpc")


def check_swaymsg() -> bool:
    """Check if swaymsg (Sway) is available.

    Returns:
        True if swaymsg exists, False otherwise
    """
    return check_command_exists("swaymsg")


def check_emacsclient() -> bool:
    """Check if emacsclient is available.

    Returns:
        True if emacsclient exists, False otherwise
    """
    return check_command_exists("emacsclient")
