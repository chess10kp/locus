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
from typing import Any, Optional, List, Dict
from core.hooks import LauncherHook


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

            # Refresh if we are still open (control actions mostly)
            # If playing a file, we usually close
            if action in ["play_file", "play_position"]:
                launcher.hide()
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


class MusicLauncher:
    def __init__(self, launcher):
        self.launcher = launcher
        self.hook = MusicHook(self)
        self.launcher.hook_registry.register_hook(self.hook)
        self.music_dir = MUSIC_DIR

        self.files_cache: List[Dict[str, str]] = []
        self.scanning = False
        self.start_scan()

    def start_scan(self):
        if self.scanning:
            return
        self.scanning = True
        thread = threading.Thread(target=self._scan_worker)
        thread.daemon = True
        thread.start()

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
        output = self._run_mpc(["status"])
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

    def populate(self, filter_text: str):
        query = filter_text
        show_queue = False

        if query.startswith("queue"):
            show_queue = True
            query = query[5:].strip()

        # Add Controls
        status = self.get_status()
        self._add_controls(status, show_queue)

        if show_queue:
            self._populate_queue(query)
        else:
            self._populate_library(query)

    def _add_controls(self, status: Dict[str, str], is_queue_mode: bool):
        state_icon = (
            "⏵"
            if status["state"] == "playing"
            else "⏸"
            if status["state"] == "paused"
            else "⏹"
        )
        header = f"{state_icon} {status['song'] or 'Stopped'}"
        meta = f"Vol: {status.get('volume')} | Rep: {status.get('repeat')} | Rnd: {status.get('random')} | Sgl: {status.get('single')}"

        # Toggle Play/Pause button
        self._add_button(text=header, metadata=meta, action="control", value="toggle")

        if is_queue_mode:
            self._add_button(
                "View Library", "Switch to file browser", "control", "view_library"
            )
        else:
            self._add_button(
                "View Queue", "Manage playback queue", "control", "view_queue"
            )

    def _add_button(self, text, metadata, action, value):
        item_data = {"type": "music_item", "action": action, "value": value}
        button = self.launcher.create_button_with_metadata(text, metadata, item_data)
        self.launcher.list_box.append(button)

    def _populate_queue(self, query):
        # mpc playlist -f '%position%\t%artist% - %title%'
        output = self._run_mpc(["playlist", "-f", "%position%\t%artist% - %title%"])
        lines = output.splitlines()

        if not lines:
            self.launcher.list_box.append(
                self.launcher.create_button_with_metadata("Queue is empty", "")
            )
            return

        for line in lines:
            parts = line.split("\t", 1)
            if len(parts) == 2:
                pos, name = parts
                if not query or query.lower() in name.lower():
                    self._add_button(
                        text=f"{pos}. {name}",
                        metadata="Click to play",
                        action="play_position",
                        value=pos,
                    )

    def _populate_library(self, query):
        if self.scanning and not self.files_cache:
            self.launcher.list_box.append(
                self.launcher.create_button_with_metadata(
                    "Scanning library...", "Please wait"
                )
            )
            return

        count = 0
        MAX_RESULTS = 50  # Limit results for performance

        for item in self.files_cache:
            if query and query.lower() not in item["name"].lower():
                continue

            self._add_button(
                text=item["name"],
                metadata=item["path"],
                action="play_file",
                value=item["path"],
            )

            count += 1
            if count >= MAX_RESULTS:
                return

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
            # Switch back to >music
            self.launcher.search_entry.set_text(">music ")
            self.launcher.on_entry_activate(self.launcher.search_entry)
