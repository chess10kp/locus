# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import subprocess
from calculator import sanitize_expr, evaluate_calculator
from hooks import LauncherHook
from typing import Any, Optional


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


class CalcLauncher:
    def __init__(self, launcher):
        self.launcher = launcher
        self.hook = CalcHook(self)
        # Register the hook with the main launcher
        launcher.hook_registry.register_hook(self.hook)

    def populate(self, expr):
        sanitized = sanitize_expr(expr)
        result, error = evaluate_calculator(sanitized)
        if error:
            label_text = f"Error: {error}"
            metadata = self.launcher.METADATA.get(label_text, "")
            button = self.launcher.create_button_with_metadata(label_text, metadata)
        else:
            label_text = f"Result: {result}"
            metadata = self.launcher.METADATA.get(label_text, "")
            button = self.launcher.create_button_with_metadata(
                label_text, metadata, result
            )
        self.launcher.list_box.append(button)
        self.launcher.list_box.queue_draw()
        self.launcher.scrolled.queue_draw()
        # Scroll to top
        vadj = self.launcher.scrolled.get_vadjustment()
        if vadj:
            vadj.set_value(0)
        self.launcher.queue_draw()
        self.launcher.current_apps = []

    def on_result_clicked(self, button, result):
        # Copy result to clipboard
        try:
            subprocess.run(["wl-copy", result], check=True)
        except subprocess.CalledProcessError:
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=result.encode(),
                    check=True,
                )
            except subprocess.CalledProcessError:
                print(f"Failed to copy to clipboard: {result}")
        self.launcher.hide()
