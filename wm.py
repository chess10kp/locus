# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: basic
# ruff: ignore

import os
import subprocess
import json
import threading
import time
from typing_extensions import final

from gi.repository import GLib

import i3ipc


@final
class Workspace:
    def __init__(self, name: str, focused: bool):
        self.name = name
        self.focused = focused
        self.num = int(name) if name.isdigit() else 999


class WMClient:
    def get_workspaces(self) -> list[Workspace]:
        raise NotImplementedError()

    def start_event_listener(self, callback) -> None:
        raise NotImplementedError()


class SwayClient(WMClient):
    def __init__(self):
        self.i3 = i3ipc.Connection()

    def get_workspaces(self) -> list[Workspace]:
        try:
            workspaces = self.i3.get_workspaces()
            return [Workspace(ws.name, ws.focused) for ws in workspaces]
        except Exception:
            return []

    def start_event_listener(self, callback) -> None:
        def on_workspace(i3, e):
            GLib.idle_add(callback)

        self.i3.on("workspace", on_workspace)
        thread = threading.Thread(target=self.i3.main)
        thread.daemon = True
        thread.start()


class HyprlandClient(WMClient):
    def __init__(self):
        self.signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")

    def get_workspaces(self) -> list[Workspace]:
        try:
            result = subprocess.run(
                ["hyprctl", "workspaces", "-j"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode != 0:
                return []

            # Get active workspace to mark focused
            active_res = subprocess.run(
                ["hyprctl", "activeworkspace", "-j"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            active_id = -1
            if active_res.returncode == 0:
                try:
                    active_data = json.loads(active_res.stdout)
                    active_id = active_data.get("id", -1)
                except Exception:
                    pass

            workspaces_data = json.loads(result.stdout)
            workspaces = []
            for ws in workspaces_data:
                # Hyprland workspaces have an ID and a name. Usually we use ID.
                # If name is different, we might prefer that.
                name = str(ws.get("id", "?"))
                is_focused = ws.get("id") == active_id
                workspaces.append(Workspace(name, is_focused))

            return workspaces
        except Exception as e:
            print(f"Hyprland error: {e}")
            return []

    def start_event_listener(self, callback) -> None:
        if not self.signature:
            return

        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
        socket_path = f"{runtime_dir}/hypr/{self.signature}/.socket2.sock"

        def listen():
            import socket

            while True:
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.connect(socket_path)

                    buffer = ""
                    while True:
                        data = s.recv(1024)
                        if not data:
                            break
                        buffer += data.decode("utf-8")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            # workspace events: workspace>>NAME, destroyworkspace>>NAME, createworkspace>>NAME, focusworkspace>>NAME
                            if "workspace" in line:
                                GLib.idle_add(callback)
                except Exception as e:
                    print(f"Hyprland socket error: {e}")
                    time.sleep(1)
                finally:
                    s.close()
                    time.sleep(1)

        thread = threading.Thread(target=listen)
        thread.daemon = True
        thread.start()


def detect_wm() -> WMClient:
    # Check for Hyprland
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return HyprlandClient()

    # Default to Sway/i3
    return SwayClient()
