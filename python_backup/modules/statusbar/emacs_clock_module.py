# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import subprocess
import json
from typing import Tuple, Optional

from gi.repository import Gtk

from core.statusbar_interface import (
    StatusbarModuleInterface,
    StatusbarUpdateMode,
    StatusbarSizeMode,
)


class EmacsClockModule(StatusbarModuleInterface):
    """Statusbar module for displaying Emacs org-mode clocked task."""

    def __init__(self, interval: int = 10, fallback_text: str = ""):
        self._interval = interval
        self._fallback_text = fallback_text

    @property
    def name(self) -> str:
        return "emacs_clock"

    @property
    def update_mode(self) -> StatusbarUpdateMode:
        return StatusbarUpdateMode.PERIODIC

    @property
    def update_interval(self) -> Optional[int]:
        return self._interval

    def create_widget(self) -> Gtk.Widget:
        label = Gtk.Label()
        label.set_name("emacs-clock-label")
        # Initial update
        self.update(label)
        return label

    def update(self, widget: Gtk.Widget) -> None:
        try:
            # Get current Emacs clocked task
            clock_info = self._get_emacs_clock_info()
            if clock_info:
                task_name = clock_info.get("task", "")
                time_spent = clock_info.get("time", "")

                if task_name and time_spent:
                    widget.set_text(f"org: {task_name}: {time_spent}")
                elif task_name:
                    widget.set_text(f"org: {task_name}")
                else:
                    widget.set_text(self._fallback_text)
            else:
                widget.set_text(self._fallback_text)
        except Exception:
            widget.set_text(self._fallback_text)

    def _get_emacs_clock_info(self) -> Optional[dict]:
        """Get current Emacs clock information using org-clock.el."""
        try:
            # Try to get clock info using emacsclient
            # The clock string has format: "[HH:MM] (Task Name)"
            emacs_script = """
            (let ((inhibit-message t)
                (message-log-max nil))
            (with-temp-message ""
                (if (org-clock-is-active)
                    (let* ((clock-string-raw (org-clock-get-clock-string))
                        (plain (substring-no-properties clock-string-raw))
                        (bracket1 (string-search "[" plain))
                        (bracket2 (string-search "]" plain))
                        (paren1 (string-search "(" plain))
                        (paren2 (string-search ")" plain))
                        (time-str (if (and bracket1 bracket2)
                                        (substring plain (+ bracket1 1) bracket2)
                                    ""))
                        (task-name (if (and paren1 paren2)
                                        (substring plain (+ paren1 1) paren2)
                                        "")))
                    ;; Use 'external-debugging-output' or just ensure it's wrapped
                    (princ (json-encode `((task . ,task-name) (time . ,time-str)))))
                (princ "null"))))
            """

            result = subprocess.run(
                ["emacsclient", "--quiet", "-e", emacs_script],
                capture_output=True,
                text=True,
                timeout=3,
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                # emacsclient wraps the output in quotes with escaped JSON
                # e.g., "{\"task\":\"...\",\"time\":\"...\"}"
                # Decode the string literal (unescape escaped quotes)
                if output.startswith('"') and output.endswith('"'):
                    # Use codecs to decode the escaped string
                    import codecs

                    output = codecs.decode(output[1:-1], "unicode_escape")
                if output and output != "null":
                    return json.loads(output)

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
            json.JSONDecodeError,
        ):
            pass

        return None

    def get_size_mode(self) -> Tuple[StatusbarSizeMode, Optional[Tuple[int, int]]]:
        return StatusbarSizeMode.DEFAULT, None

    def get_styles(self) -> Optional[str]:
        return """
        #emacs-clock-label {
            font-size: 16px;
            font-weight: 500;
        }
        """
