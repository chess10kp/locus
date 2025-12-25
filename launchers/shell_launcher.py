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
from typing import Any, Optional


class ShellHook(LauncherHook):
    def __init__(self, shell_launcher):
        self.shell_launcher = shell_launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """Handle shell command execution button clicks"""
        data_str = (
            item_data if isinstance(item_data, str) else str(item_data.get("", ""))
        )
        if data_str.startswith("exec:"):
            command = data_str[5:]  # Remove "exec:" prefix
            self.shell_launcher.execute_command(command)
            launcher.hide()
            return True
        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle shell enter key"""
        if text.startswith(">shell") and len(text) > 6:
            command = text[6:].strip()
            if command:
                self.shell_launcher.execute_command(command)
                return True
        elif text.startswith(">sh") and len(text) > 3:
            command = text[3:].strip()
            if command:
                self.shell_launcher.execute_command(command)
                return True
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle shell tab completion"""
        if text.startswith(">shell") or (text.startswith(">sh") and len(text) <= 4):
            return ">shell "
        return None


class ShellLauncher(LauncherInterface):
    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.hook = ShellHook(self)
        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, "hook_registry"):
            main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self):
        return ["shell", "sh"]

    @property
    def name(self):
        return "shell"

    def get_size_mode(self):
        return LauncherSizeMode.DEFAULT, None

    def handles_enter(self):
        return True

    def handle_enter(self, query: str, launcher_core) -> bool:
        if query:
            self.execute_command(query)
            return True
        return False

    def populate(self, query: str, launcher_core):
        if not query:
            # Show help text when no query
            label_text = "Enter shell command to execute"
            metadata = "Enter command"
            launcher_core.add_launcher_result(
                label_text, metadata, index=1, icon_name="utilities-terminal"
            )
        else:
            # Show the command that will be executed
            label_text = f"Execute: {query}"
            metadata = "Run command"
            launcher_core.add_launcher_result(
                label_text,
                metadata,
                index=1,
                action_data=f"exec:{query}",
                icon_name="utilities-terminal",
            )

        # Scroll to top
        vadj = launcher_core.scrolled.get_vadjustment()
        if vadj:
            vadj.set_value(0)
        launcher_core.current_apps = []

    def execute_command(self, command: str):
        """Execute the shell command"""
        try:
            # Clean environment for child processes
            env = dict(os.environ.items())
            env.pop("LD_PRELOAD", None)  # Remove LD_PRELOAD for child processes

            # Use shell=True to allow shell features like pipes, redirects, etc.
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                env=env,
                timeout=30,  # 30 second timeout
            )

            pass

        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass
