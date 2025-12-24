# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import os
import subprocess
import datetime
import logging


from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from utils.deps import check_command_exists

logger = logging.getLogger("ScreenshotLauncher")


class ScreenshotHook(LauncherHook):
    def __init__(self, screenshot_launcher):
        self.screenshot_launcher = screenshot_launcher

    def on_select(self, launcher, item_data) -> bool:
        if isinstance(item_data, dict) and item_data.get("type") == "screenshot":
            mode = item_data.get("mode")
            if mode in ["full", "area"]:
                self.screenshot_launcher.take_screenshot(mode)
                launcher.hide()
                return True
        return False

    def on_enter(self, launcher, text):
        return False

    def on_tab(self, launcher, text):
        return None


class ScreenshotLauncher(LauncherInterface):
    @classmethod
    def check_dependencies(cls):
        if not check_command_exists("grim"):
            return False, "grim not found"
        if not check_command_exists("slurp"):
            return False, "slurp not found"
        return True, ""

    def __init__(self, main_launcher=None):
        if main_launcher:
            self.hook = ScreenshotHook(self)
            main_launcher.hook_registry.register_hook(self.hook)
        self.screenshot_dir = os.path.expanduser("~/Pictures/Screenshots")

    @property
    def command_triggers(self):
        return ["screenshot", "ss"]

    @property
    def name(self):
        return "screenshot"

    def get_size_mode(self):
        return (LauncherSizeMode.DEFAULT, None)

    def populate(self, query, launcher_core):
        if not query.strip():
            launcher_core.add_launcher_result(
                "Screenshot Capture",
                "Choose capture mode",
                index=1,
            )
            launcher_core.add_launcher_result(
                "Full Screen",
                "Capture entire display",
                index=2,
                action_data={"type": "screenshot", "mode": "full"},
                icon_name="camera-photo",
            )
            launcher_core.add_launcher_result(
                "Select Area",
                "Click and drag to select region",
                index=3,
                action_data={"type": "screenshot", "mode": "area"},
                icon_name="image-x-generic",
            )
            return

        query_lower = query.lower()
        if "full" in query_lower or "screen" in query_lower:
            launcher_core.add_launcher_result(
                "Full Screen Screenshot",
                "Capture entire display",
                index=1,
                action_data={"type": "screenshot", "mode": "full"},
                icon_name="camera-photo",
            )
        if "area" in query_lower or "select" in query_lower:
            launcher_core.add_launcher_result(
                "Select Area Screenshot",
                "Click and drag to select region",
                index=2,
                action_data={"type": "screenshot", "mode": "area"},
                icon_name="image-x-generic",
            )

    def take_screenshot(self, mode):
        try:
            os.makedirs(self.screenshot_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = os.path.join(self.screenshot_dir, filename)

            if mode == "full":
                result = subprocess.run(
                    ["grim", filepath], capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    logger.info(f"Screenshot saved: {filepath}")
                    return True
                else:
                    logger.error(f"Failed: {result.stderr}")
                    return False

            elif mode == "area":
                cmd = f'grim -g "$(slurp)" "{filepath}"'
                result = subprocess.run(
                    ["sh", "-c", cmd], capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    logger.info(f"Screenshot saved: {filepath}")
                    return True
                else:
                    logger.error(f"Failed: {result.stderr}")
                    return False

        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return False

    def cleanup(self):
        pass
