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
from typing import Any, Optional, List, Dict
from core.hooks import LauncherHook


class RefileHook(LauncherHook):
    def __init__(self, refile_launcher):
        self.refile_launcher = refile_launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """Handle workspace selection"""
        if isinstance(item_data, dict) and item_data.get("type") == "refile_workspace":
            workspace_name = item_data.get("workspace")
            if workspace_name:
                self.refile_launcher.swap_with_workspace(workspace_name)
                launcher.hide()
                return True
        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle enter on refile command"""
        if text.startswith(">refile"):
            workspace = text[7:].strip()
            if workspace:
                self.refile_launcher.swap_with_workspace(workspace)
                launcher.hide()
                return True
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle tab completion for workspaces"""
        if text.startswith(">refile"):
            partial = text[7:].strip()
            workspaces = self.refile_launcher.get_workspaces()
            matching = [ws for ws in workspaces if ws.startswith(partial)]
            if matching and len(matching) == 1:
                return f">refile {matching[0]}"
        return None


class RefileLauncher:
    def __init__(self, launcher):
        self.launcher = launcher
        self.hook = RefileHook(self)
        self.launcher.hook_registry.register_hook(self.hook)

    def get_workspaces(self) -> List[str]:
        """Get list of all workspace names"""
        try:
            result = subprocess.run(
                ["swaymsg", "-t", "get_workspaces"],
                capture_output=True,
                text=True,
                check=True
            )
            workspaces = json.loads(result.stdout)
            return [ws["name"] for ws in workspaces]
        except Exception as e:
            print(f"Error getting workspaces: {e}")
            return []

    def get_current_workspace(self) -> Optional[str]:
        """Get the currently focused workspace"""
        try:
            result = subprocess.run(
                ["swaymsg", "-t", "get_workspaces"],
                capture_output=True,
                text=True,
                check=True
            )
            workspaces = json.loads(result.stdout)
            for ws in workspaces:
                if ws.get("focused"):
                    return ws["name"]
            return None
        except Exception as e:
            print(f"Error getting current workspace: {e}")
            return None

    def swap_with_workspace(self, target_workspace: str):
        """Swap current workspace with target workspace using the refile.sh logic"""
        try:
            current_workspace = self.get_current_workspace()
            if not current_workspace:
                subprocess.run(
                    ["notify-send", "Workspace Swap", "Failed to get current workspace"]
                )
                return

            if target_workspace == current_workspace:
                subprocess.run(
                    ["notify-send", "Workspace Swap", "Cannot swap a workspace with itself"]
                )
                return

            # Check if target workspace exists
            workspaces = self.get_workspaces()
            if target_workspace not in workspaces:
                subprocess.run(
                    ["notify-send", "Workspace Swap", f"Workspace '{target_workspace}' does not exist"]
                )
                return

            # Execute the swap logic from refile.sh
            subprocess.run(["swaymsg", "workspace", "tmp_swap_workspace"])
            subprocess.run(["swaymsg", f"[workspace=\"{current_workspace}\"] move container to workspace tmp_swap_workspace"])
            subprocess.run(["swaymsg", "workspace", target_workspace])
            subprocess.run(["swaymsg", f"[workspace=\"{target_workspace}\"] move container to workspace {current_workspace}"])
            subprocess.run(["swaymsg", "workspace", "tmp_swap_workspace"])
            subprocess.run(["swaymsg", f"[workspace=\"tmp_swap_workspace\"] move container to workspace {target_workspace}"])
            subprocess.run(["swaymsg", "workspace", current_workspace])

        except Exception as e:
            print(f"Error swapping workspaces: {e}")
            subprocess.run(
                ["notify-send", "Workspace Swap", f"Error: {e}"]
            )

    def populate(self, filter_text: str = ""):
        """Populate the launcher with workspace options"""
        current_workspace = self.get_current_workspace()
        workspaces = self.get_workspaces()

        if not workspaces:
            button = self.launcher.create_button_with_metadata(
                "No workspaces found", "Unable to get workspace list"
            )
            self.launcher.list_box.append(button)
            return

        # Add header with current workspace info
        if current_workspace:
            header = f"Current workspace: {current_workspace}"
            metadata = "Select a workspace to swap with"
            button = self.launcher.create_button_with_metadata(header, metadata)
            button.set_sensitive(False)  # Make it non-clickable
            self.launcher.list_box.append(button)

        # Filter and add workspaces
        for workspace in sorted(workspaces):
            # Skip current workspace
            if workspace == current_workspace:
                continue

            # Apply filter if provided
            if filter_text and filter_text.lower() not in workspace.lower():
                continue

            item_data = {"type": "refile_workspace", "workspace": workspace}
            button = self.launcher.create_button_with_metadata(
                f"Swap to: {workspace}",
                f"Exchange containers with workspace '{workspace}'",
                item_data
            )
            self.launcher.list_box.append(button)