#!/usr/bin/env python3
# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: basic
# ruff: ignore

import socket
import sys
import subprocess
import os
import shutil

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(__file__))

from core import config


def has_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def send_message(message: str):
    """Send a message to locus via Unix socket"""
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(config.SOCKET_PATH)
        client.send(message.encode("utf-8"))
        client.close()
    except Exception as e:
        print(f"Failed to send message: {e}", file=sys.stderr)
        sys.exit(1)


def run_command(cmd: str) -> str:
    """Run a shell command and return stdout stripped."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"Command failed: {cmd}", file=sys.stderr)
            return ""
    except Exception as e:
        print(f"Error running command '{cmd}': {e}", file=sys.stderr)
        return ""


def handle_volume(action: str):
    """Handle volume commands."""
    use_pamixer = has_command("pamixer")
    use_pactl = has_command("pactl")

    if use_pactl:
        if action == "up":
            run_command("pactl set-sink-volume @DEFAULT_SINK@ +5%")

        elif action == "down":
            run_command("pactl set-sink-volume @DEFAULT_SINK@ -5%")
        elif action == "mute":
            run_command("pactl set-sink-mute @DEFAULT_SINK@ toggle")

    if use_pamixer:
        if action == "up":
            run_command("pamixer --increase 5")
        elif action == "down":
            run_command("pamixer --decrease 5")
        elif action == "mute":
            run_command("pamixer --toggle-mute")

        # Get current volume
        volume = run_command("pamixer --get-volume")
    else:
        # Fallback to amixer
        if action == "up":
            run_command("amixer set Master 5%+")
        elif action == "down":
            run_command("amixer set Master 5%-")
        elif action == "mute":
            run_command("amixer set Master toggle")

        # Get current volume from amixer
        output = run_command("amixer get Master")
        if output:
            import re

            match = re.search(r"\[(\d+)%\]", output)
            if match:
                volume = match.group(1)
                muted = "[off]" in output
            else:
                volume = None
                muted = False
        else:
            volume = None
            muted = False

    if volume:
        try:
            vol_int = int(volume)
            # Check if muted
            if vol_int == 0 or muted:
                send_message("progress:volume:0:mute")
            else:
                send_message(f"progress:volume:{vol_int}")
        except ValueError:
            print(f"Invalid volume value: {volume}", file=sys.stderr)
    else:
        print("Failed to get volume", file=sys.stderr)


def handle_brightness(action: str):
    """Handle brightness commands."""
    if action == "up":
        run_command(config.BRIGHT_UP_CMD)
    elif action == "down":
        run_command(config.BRIGHT_DOWN_CMD)

    # Get current brightness
    brightness = run_command(config.BRIGHT_GET_CMD)
    if brightness:
        try:
            bright_float = float(brightness)
            bright_int = int(bright_float)
            send_message(f"progress:brightness:{bright_int}")
        except ValueError:
            print(f"Invalid brightness value: {brightness}", file=sys.stderr)
    else:
        print("Failed to get brightness", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "volume":
        handle_volume(sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] == "brightness":
        handle_brightness(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "launcher":
         if len(sys.argv) > 2:
             # Check for special launcher commands
             if sys.argv[2] in ["resume", "fresh"]:
                 command = sys.argv[2]
                 # Check if there's an app name after the command
                 if len(sys.argv) > 3:
                     app_name = " ".join(sys.argv[3:])
                     send_message(f"launcher:{command} {app_name}")
                 else:
                     send_message(f"launcher:{command}")
             elif sys.argv[2] == "dmenu":
                 # Read options from stdin
                 options = sys.stdin.read()
                 send_message(f"launcher dmenu:{options}")
             else:
                 # Regular launcher with app name
                 app_name = " ".join(sys.argv[2:])
                 send_message(f"launcher {app_name}")
         else:
             send_message("launcher")
    elif len(sys.argv) >= 2:
        message = " ".join(sys.argv[1:])
        send_message(message)
    else:
        print(
            "Usage: python locus_client.py volume|brightness up|down|mute|get | launcher [resume|fresh] [app] | <message>",
            file=sys.stderr,
        )
        sys.exit(1)
