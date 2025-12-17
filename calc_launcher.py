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


class CalcLauncher:
    def __init__(self, launcher):
        self.launcher = launcher

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
            button = self.launcher.create_button_with_metadata(label_text, metadata)
            button.connect("clicked", self.on_result_clicked, result)
        self.launcher.list_box.append(button)
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
