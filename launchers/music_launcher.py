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
import threading
from typing import Any, Optional, List, Dict, Tuple
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from utils.launcher_utils import LauncherEnhancer


class MusicHook(LauncherHook):
    def __init__(self, music_launcher):
        self.music_launcher = music_launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """Handle music item selection"""
        if isinstance(item_data, dict) and item_data.get("type") == "music_item":
            action = item_data.get("action")
            value = item_data.get("value")

            if action == "play_file":
                self.music_launcher.play_file(value)
            elif action == "play_position":
                self.music_launcher.play_position(value)
            elif action == "queue_remove":
                self.music_launcher.remove_from_queue(value)
            elif action == "control":
                self.music_launcher.control(value)
            elif action == "view_queue":
                # Set search text to >music queue to trigger populate
                launcher.search_entry.set_text(">music queue")
                launcher.on_entry_activate(launcher.search_entry)
            elif action == "view_library":
                # Set search text to >music to trigger library view
                launcher.search_entry.set_text(">music")
                launcher.on_entry_activate(launcher.search_entry)

            # Refresh if we are still open (control actions mostly)
            # If playing a file, we usually close
            if action in ["play_file", "play_position"]:
                launcher.hide()
            elif action in ["view_queue", "view_library"]:
                # Already handled by setting search text
                pass
            else:
                # Refresh the view
                current_text = launcher.search_entry.get_text()
                launcher.populate_apps(current_text)

            return True
        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle enter on music commands"""
        if text.startswith(">music"):
            cmd = text[6:].strip()
            if cmd in ["clear", "pause", "play"]:
                self.music_launcher.control(cmd)
                launcher.hide()
                return True

            if cmd == "":
                # Just refresh/populate default view
                self.music_launcher.populate("")
                return True
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        if text.startswith(">music"):
            # Could implement completion for subcommands
            pass
        return None


from core.config import MUSIC_DIR


class MusicLauncher(LauncherInterface):
    def __init__(self, main_launcher=None):
        if main_launcher:
            self.hook = MusicHook(self)
            main_launcher.hook_registry.register_hook(self.hook)

        self.music_dir = MUSIC_DIR
        self.files_cache: List[Dict[str, str]] = []
        self.scanning = False
        self.scanned = False

    @property
    def command_triggers(self) -> list:
        return ["music", "mu"]

    @property
    def name(self) -> str:
        return "music"

    def get_size_mode(self) -> Tuple[LauncherSizeMode, Optional[Tuple[int, int]]]:
        return (LauncherSizeMode.DEFAULT, None)

    def _scan_worker(self):
        # We'll use os.walk for portability in python
        exts = (".mp3", ".flac", ".opus", ".ogg", ".m4a", ".wav")
        new_cache = []

        try:
            for root, _, files in os.walk(self.music_dir):
                for f in files:
                    if f.lower().endswith(exts):
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, self.music_dir)
                        new_cache.append({"name": f, "path": rel_path})
        except Exception as e:
            print(f"Music scan error: {e}")

        self.files_cache = new_cache
        self.scanning = False

    def _run_mpc(self, args: List[str]) -> str:
        try:
            result = subprocess.run(["mpc"] + args, capture_output=True, text=True)
            return result.stdout.strip()
        except Exception as e:
            print(f"MPC Error: {e}")
            return ""

    def get_status(self) -> Dict[str, str]:
        # Get status lines
        try:
            result = subprocess.run(
                ["mpc", "status"], capture_output=True, text=True, timeout=1
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                return {
                    "state": "stopped",
                    "song": "MPD not running",
                    "volume": "",
                    "repeat": "off",
                    "random": "off",
                    "single": "off",
                    "consume": "off",
                }
        except Exception:
            return {
                "state": "stopped",
                "song": "MPC not available",
                "volume": "",
                "repeat": "off",
                "random": "off",
                "single": "off",
                "consume": "off",
            }

        status = {
            "state": "stopped",
            "song": "",
            "volume": "",
            "repeat": "off",
            "random": "off",
            "single": "off",
            "consume": "off",
        }

        lines = output.splitlines()
        if not lines:
            return status

        # Parse status
        # Example output:
        # The Song Name
        # [playing] #1/5   0:05/3:40 (2%)
        # volume:100%   repeat: off   random: off   single: off   consume: off

        if len(lines) >= 1:
            if lines[0].startswith("volume:"):
                # Stopped state
                pass
            else:
                status["song"] = lines[0]

        for line in lines:
            if "[playing]" in line:
                status["state"] = "playing"
            elif "[paused]" in line:
                status["state"] = "paused"

            if "volume:" in line:
                # Parse flags
                for part in line.split("   "):
                    if ":" in part:
                        k, v = part.split(":", 1)
                        status[k.strip()] = v.strip()

        return status

    def populate(self, query: str, launcher_core) -> None:
        if not self.scanned:
            self.scanned = True
            self._scan_worker()

        show_queue = False

        if query.startswith("queue"):
            show_queue = True
            query = query[5:].strip()

        # Add Controls
        status = self.get_status()
        self._add_controls(status, show_queue, launcher_core)

        if show_queue:
            self._populate_queue(query, launcher_core)
        else:
            self._populate_library(query, launcher_core)

    def _add_controls(self, status: Dict[str, str], is_queue_mode: bool, launcher_core):
        state_icon = (
            "⏵"
            if status["state"] == "playing"
            else "⏸"
            if status["state"] == "paused"
            else "⏹"
        )
        header = f"{state_icon} {status['song'] or 'Stopped'}"
        meta = f"Vol: {status.get('volume')} | Rep: {status.get('repeat')} | Rnd: {status.get('random')} | Sgl: {status.get('single')}"

        # Toggle Play/Pause button with hint
        self._add_button(
            text=header,
            metadata=meta,
            action="control",
            value="toggle",
            launcher_core=launcher_core,
            index=1,
        )

        if is_queue_mode:
            self._add_button(
                "Clear Queue",
                "Remove all songs from queue",
                "control",
                "clear",
                launcher_core,
                index=2,
            )
            self._add_button(
                "View Library",
                "Switch to file browser",
                "control",
                "view_library",
                launcher_core,
                index=3,
            )
        else:
            self._add_button(
                "View Queue",
                "Manage playback queue",
                "control",
                "view_queue",
                launcher_core,
                index=2,
            )

    def _add_button(self, text, metadata, action, value, launcher_core, index=None):
        item_data = {"type": "music_item", "action": action, "value": value}
        launcher_core.add_launcher_result(
            text, metadata, index=index, action_data=item_data
        )

    def _populate_queue(self, query, launcher_core):
        # Get playlist with position and filename
        output = self._run_mpc(["playlist", "-f", "%position%\t%file%"])
        lines = output.splitlines() if output else []

        if not lines or not any(line.strip() for line in lines):
            launcher_core.add_launcher_result("Queue is empty", "")
            return

        index = 4  # Start after control buttons (1=toggle, 2=clear, 3=view library)
        for line in lines:
            if not line.strip():
                continue

            # Parse position and filename
            if "\t" in line:
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    pos, filename = parts
                else:
                    continue
            else:
                # Plain format, try to extract position from start
                if " " in line:
                    pos, filename = line.split(" ", 1)
                else:
                    pos = str(index - 3)  # Use position based on loop
                    filename = line

            # Clean up the filename for display
            display_name = filename
            if display_name:
                # Extract just filename from path
                if "/" in display_name:
                    display_name = display_name.split("/")[-1]
                # Remove file extension
                if "." in display_name:
                    display_name = ".".join(display_name.split(".")[:-1])

            # Filter by search query if provided
            if not query or query.lower() in display_name.lower():
                self._add_button(
                    text=f"{pos}. {display_name or filename}",
                    metadata="Click to play | Alt+Enter to remove",
                    action="play_position",
                    value=pos,
                    launcher_core=launcher_core,
                    index=index if index <= 9 else None,  # Only show hints for 3-9
                )
                index += 1
                if index > 9:  # Stop showing hints after 9
                    break

    def _populate_library(self, query, launcher_core):
        if self.scanning and not self.files_cache:
            launcher_core.add_launcher_result("Scanning library...", "Please wait")
            return

        if not self.files_cache:
            launcher_core.add_launcher_result(
                "No music files found", f"Check {self.music_dir} directory"
            )
            return

        count = 0
        MAX_RESULTS = 50  # Limit results for performance
        index = 3  # Start after control buttons (1=toggle, 2=view mode)

        for item in self.files_cache:
            if query and query.lower() not in item["name"].lower():
                continue

            self._add_button(
                text=item["name"],
                metadata=item["path"],
                action="play_file",
                value=item["path"],
                launcher_core=launcher_core,
                index=index if index <= 9 else None,  # Only show hints for 3-9
            )
            index += 1
            if index > 9:  # Stop showing hints after 9
                break

            count += 1
            if count >= MAX_RESULTS:
                return

        if count == 0 and query:
            launcher_core.list_box.append(
                launcher_core.create_button_with_metadata(
                    f"No matches for '{query}'", ""
                )
            )

    def play_file(self, rel_path):
        self._run_mpc(["add", rel_path])
        # If stopped, play. If playing, it adds to queue.
        # Using 'play' might restart current song if playing.
        status = self.get_status()
        if status["state"] != "playing":
            self._run_mpc(["play"])

    def play_position(self, pos):
        self._run_mpc(["play", pos])

    def remove_from_queue(self, pos):
        self._run_mpc(["del", pos])

    def start_scan(self):
        """Start a background scan of the music directory."""
        if not self.scanning:
            self.scanning = True
            thread = threading.Thread(target=self._scan_worker, daemon=True)
            thread.start()

    def control(self, command):
        if command == "toggle":
            self._run_mpc(["toggle"])
        elif command == "play":
            self._run_mpc(["play"])
        elif command == "pause":
            self._run_mpc(["pause"])
        elif command == "next":
            self._run_mpc(["next"])
        elif command == "prev":
            self._run_mpc(["prev"])
        elif command == "clear":
            self._run_mpc(["clear"])
        elif command == "rescan":
            self._run_mpc(["update"])
            self.start_scan()  # Rescan local cache too
        elif command == "view_queue":
            # Handled in hook return
            pass
        elif command == "view_library":
            # This would be handled by the main launcher
            pass
