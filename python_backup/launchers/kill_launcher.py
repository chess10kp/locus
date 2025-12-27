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
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from typing import Any, Optional, Tuple


class KillHook(LauncherHook):
    def __init__(self, kill_launcher):
        self.kill_launcher = kill_launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """Handle process kill button clicks"""
        if isinstance(item_data, int):
            self.kill_launcher.kill_process(item_data)
            launcher.hide()
            return True
        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle kill enter key"""
        # For now, no specific enter handling for kill
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle kill tab completion"""
        if text.startswith(">kill") or (text.startswith(">ki") and len(text) <= 4):
            return ">kill "
        return None


class KillLauncher(LauncherInterface):
    def __init__(self, main_launcher=None):
        if main_launcher:
            self.hook = KillHook(self)
            main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self) -> list:
        return ["kill", "ki"]

    @property
    def name(self) -> str:
        return "kill"

    def get_size_mode(self) -> Tuple[LauncherSizeMode, Optional[Tuple[int, int]]]:
        return LauncherSizeMode.DEFAULT, None

    def populate(self, query: str, launcher_core) -> None:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        if result.returncode != 0:
            label_text = "Failed to get processes"
            launcher_core.add_launcher_result(label_text, "")
            launcher_core.current_apps = []
            return

        lines = result.stdout.splitlines()
        processes = []
        for line in lines[1:]:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            try:
                pid = int(parts[1])
                cpu = float(parts[2])
                mem = float(parts[3])
                cmd = parts[10]
                if pid != os.getpid():  # exclude self
                    processes.append((pid, cpu, mem, cmd))
            except ValueError:
                continue

        # sort by -cpu, -mem
        processes.sort(key=lambda x: (-x[1], -x[2]))

        for pid, cpu, mem, cmd in processes[:50]:  # limit to 50
            label_text = f"{cmd} (CPU: {cpu:.1f}%, MEM: {mem:.1f}%)"
            launcher_core.add_launcher_result(
                label_text, "", index=None, action_data=pid
            )
        launcher_core.current_apps = []

    def kill_process(self, pid):
        subprocess.run(["kill", str(pid)])

    def on_kill_clicked(self, button, pid):
        try:
            subprocess.run(["kill", str(pid)], check=True)
            # refresh would be handled by the main launcher
        except subprocess.CalledProcessError:
            print(f"Failed to kill {pid}")
