# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import subprocess
import os
import socket
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from core.config import BRIGHT_UP_CMD, BRIGHT_DOWN_CMD, BRIGHT_GET_CMD, SOCKET_PATH
from typing import Any, Optional


class BrightnessHook(LauncherHook):
    def __init__(self, brightness_launcher):
        self.brightness_launcher = brightness_launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """Handle brightness control selections"""
        data_str = (
            item_data if isinstance(item_data, str) else str(item_data.get("", ""))
        )
        if data_str == "brightness:up":
            self.adjust_brightness("up")
            launcher.selected_row = None
            launcher.populate_apps(">brightness")
            return True
        elif data_str == "brightness:down":
            self.adjust_brightness("down")
            launcher.selected_row = None
            launcher.populate_apps(">brightness")
            return True
        elif data_str.startswith("brightness:set:"):
            # Extract percentage from "brightness:set:50"
            try:
                pct = int(data_str.split(":")[-1])
                self.set_brightness(pct)
                launcher.selected_row = None
                launcher.populate_apps(">brightness")
                return True
            except ValueError:
                pass
        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle enter key for brightness commands"""
        if text.startswith(">brightness "):
            cmd = text[11:].strip().lower()
            if cmd in ["up", "down"]:
                self.brightness_launcher.adjust_brightness(cmd)
                launcher.hide()
                return True
            elif cmd.isdigit():
                pct = int(cmd)
                if 0 <= pct <= 100:
                    self.brightness_launcher.set_brightness(pct)
                    launcher.hide()
                    return True
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle tab completion for brightness commands"""
        if text.startswith(">brightness") or (
            text.startswith(">bright") and len(text) <= 8
        ):
            return ">brightness "
        return None


class BrightnessLauncher(LauncherInterface):
    @classmethod
    def check_dependencies(cls) -> tuple[bool, str]:
        """Check if brightness utilities are available."""
        from utils.deps import check_brightness_utilities

        error = check_brightness_utilities()
        return error is None, error or ""

    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.hook = BrightnessHook(self)

        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, "hook_registry"):
            main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self):
        return ["brightness", "bright"]

    @property
    def name(self):
        return "brightness"

    def get_size_mode(self):
        return LauncherSizeMode.DEFAULT, None

    def handles_enter(self):
        return True

    def handle_enter(self, query: str, launcher_core) -> bool:
        if query:
            cmd = query.strip().lower()
            if cmd in ["up", "down"]:
                self.adjust_brightness(cmd)
                launcher_core.hide()
                return True
            elif cmd.isdigit():
                pct = int(cmd)
                if 0 <= pct <= 100:
                    self.set_brightness(pct)
                    launcher_core.hide()
                    return True
        return False

    def populate(self, query, launcher_core):
        """Populate the brightness control interface"""
        current_brightness = self.get_current_brightness()

        if current_brightness is not None:
            # Main brightness display
            title = f"Brightness: {current_brightness}%"
            metadata = "Current screen brightness level"
            launcher_core.add_launcher_result(title, metadata, index=1)

            # Control options
            launcher_core.add_launcher_result(
                "Increase Brightness",
                "Click to increase brightness by 5%",
                index=2,
                action_data="brightness:up",
            )
            launcher_core.add_launcher_result(
                "Decrease Brightness",
                "Click to decrease brightness by 5%",
                index=3,
                action_data="brightness:down",
            )

            # Preset brightness levels
            presets = [25, 50, 75, 100]
            for i, pct in enumerate(presets, 4):
                launcher_core.add_launcher_result(
                    f"Set to {pct}%",
                    f"Set brightness to {pct}%",
                    index=i,
                    action_data=f"brightness:set:{pct}",
                )
        else:
            launcher_core.add_launcher_result(
                "Brightness control unavailable",
                "brightnessctl not found or not working",
                index=1,
            )

        launcher_core.current_apps = []

    def get_current_brightness(self) -> Optional[int]:
        """Get current brightness percentage"""
        try:
            # Get current brightness value
            current_result = subprocess.run(
                ["brightnessctl", "get"],
                capture_output=True,
                text=True,
                env=dict(os.environ, PATH="/usr/bin:/bin"),
            )
            # Get max brightness value
            max_result = subprocess.run(
                ["brightnessctl", "max"],
                capture_output=True,
                text=True,
                env=dict(os.environ, PATH="/usr/bin:/bin"),
            )

            if current_result.returncode == 0 and max_result.returncode == 0:
                current = int(current_result.stdout.strip())
                max_val = int(max_result.stdout.strip())
                if max_val > 0:
                    percentage = int((current * 100) / max_val)
                    return max(0, min(100, percentage))
        except (ValueError, subprocess.SubprocessError):
            pass
        return None

    def _send_message(self, message: str):
        """Send a message to locus via Unix socket"""
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(SOCKET_PATH)
            client.send(message.encode("utf-8"))
            client.close()
        except Exception:
            pass  # Ignore errors when sending messages

    def adjust_brightness(self, direction: str):
        """Adjust brightness up or down"""
        cmd = BRIGHT_UP_CMD if direction == "up" else BRIGHT_DOWN_CMD
        try:
            subprocess.run(
                cmd, shell=True, check=True, env=dict(os.environ, PATH="/usr/bin:/bin")
            )
            # Send progress message to status bar
            current = self.get_current_brightness()
            if current is not None:
                self._send_message(f"progress:brightness:{current}")
        except subprocess.SubprocessError:
            pass

    def set_brightness(self, percentage: int):
        """Set brightness to specific percentage"""
        try:
            # Get max brightness value
            max_result = subprocess.run(
                ["brightnessctl", "max"],
                capture_output=True,
                text=True,
                env=dict(os.environ, PATH="/usr/bin:/bin"),
            )
            if max_result.returncode == 0:
                max_brightness = int(max_result.stdout.strip())
                target = int((percentage / 100.0) * max_brightness)
                # Set the brightness
                subprocess.run(
                    ["brightnessctl", "set", str(target)],
                    check=True,
                    env=dict(os.environ, PATH="/usr/bin:/bin"),
                )
                # Send progress message to status bar
                self._send_message(f"progress:brightness:{percentage}")
        except (ValueError, subprocess.SubprocessError):
            pass
