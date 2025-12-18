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
from utils import sanitize_expr, evaluate_calculator
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from typing import Any, Optional, Tuple


class CalcHook(LauncherHook):
    def __init__(self, calc_launcher):
        self.calc_launcher = calc_launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """Handle calculator result button clicks"""
        if isinstance(item_data, (int, float, str)):
            # Copy result to clipboard
            self.calc_launcher.on_result_clicked(None, str(item_data))
            return True
        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle calculator enter key"""
        if text.startswith(">calc") and len(text) > 5:
            expr = text[5:].strip()
            if expr:
                sanitized = sanitize_expr(expr)
                result, error = evaluate_calculator(sanitized)
                if error:
                    print(f"Calculator error: {error}")
                    # Do not hide, let user correct
                else:
                    self.calc_launcher.on_result_clicked(None, str(result))
                    return True
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle calculator tab completion"""
        # No specific tab completion for calculator yet
        return None


class CalcLauncher(LauncherInterface):
    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.hook = CalcHook(self)
        # Register with launcher registry
        from core.launcher_registry import launcher_registry
        launcher_registry.register(self)
        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, 'hook_registry'):
            main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self):
        return ["calc"]

    @property
    def name(self):
        return "calculator"

    def get_size_mode(self):
        return LauncherSizeMode.DEFAULT, None

    def handles_enter(self):
        return True

    def handle_enter(self, query: str, launcher_core) -> bool:
        if query:
            sanitized = sanitize_expr(query)
            result, error = evaluate_calculator(sanitized)
            if error:
                print(f"Calculator error: {error}")
                # Don't hide, let user correct
            else:
                self.on_result_clicked(None, str(result))
                return True
        return False

    def populate(self, expr, launcher_core):
        sanitized = sanitize_expr(expr)
        result, error = evaluate_calculator(sanitized)
        if error:
            label_text = f"Error: {error}"
            metadata = launcher_core.METADATA.get(label_text, "")
            button = launcher_core.create_button_with_metadata(label_text, metadata)
        else:
            label_text = f"Result: {result}"
            metadata = launcher_core.METADATA.get(label_text, "")
            button = launcher_core.create_button_with_metadata(
                label_text, metadata, result
            )
        launcher_core.list_box.append(button)
        launcher_core.list_box.queue_draw()
        launcher_core.scrolled.queue_draw()
        # Scroll to top
        vadj = launcher_core.scrolled.get_vadjustment()
        if vadj:
            vadj.set_value(0)
        launcher_core.queue_draw()
        launcher_core.current_apps = []

    def on_result_clicked(self, button, result):
        # Copy result to clipboard
        try:
            # Clean environment for child processes
            env = dict(os.environ.items())
            env.pop("LD_PRELOAD", None)  # Remove LD_PRELOAD for child processes
            subprocess.run(["wl-copy", result], check=True, env=env)
        except subprocess.CalledProcessError:
            try:
                # Clean environment for child processes
                env = dict(os.environ.items())
                env.pop("LD_PRELOAD", None)  # Remove LD_PRELOAD for child processes
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=result.encode(),
                    check=True,
                    env=env,
                )
            except subprocess.CalledProcessError:
                print(f"Failed to copy to clipboard: {result}")
        self.launcher.hide()
