# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import os
from typing import Any, Optional, Tuple, List
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from utils.scroll_config_parser import ScrollConfigParser, Keybinding


class KeybindingHook(LauncherHook):
    def __init__(self, launcher):
        self.launcher = launcher

    def on_select(self, launcher, item_data: Any) -> bool:
        """No action on select - just viewing keybindings."""
        return False  # Don't hide launcher, stay open

    def on_enter(self, launcher, text: str) -> bool:
        """No action on enter."""
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """No tab completion."""
        return None


class KeybindingLauncher(LauncherInterface):
    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.hook = KeybindingHook(self)

        if main_launcher and hasattr(main_launcher, "hook_registry"):
            main_launcher.hook_registry.register_hook(self.hook)

        # Initialize parser and cache
        self.parser = None
        self.bindings = None
        self.config_mtime = 0

    @property
    def command_triggers(self) -> List[str]:
        return ["key", "keys", "kb"]

    @property
    def name(self) -> str:
        return "keybinding"

    def get_size_mode(self) -> Tuple[LauncherSizeMode, Optional[Tuple[int, int]]]:
        return LauncherSizeMode.DEFAULT, None

    def _reload_config(self) -> None:
        """Reload config file if it has changed."""
        try:
            parser = ScrollConfigParser()
            config_path = parser.config_path

            # Check if file has been modified
            current_mtime = os.path.getmtime(config_path)
            if self.bindings is None or current_mtime != self.config_mtime:
                self.bindings = parser.parse()
                self.config_mtime = current_mtime
        except Exception:
            # If parsing fails, clear bindings to avoid stale data
            self.bindings = {"": []}

    def _extract_meaningful_command(self, command: str) -> str:
        """Extract meaningful part for display."""
        # Remove mode commands
        if " mode " in command:
            command = command.split(" mode ")[0]
        # For exec commands, show just the executable
        if command.startswith("exec "):
            parts = command.split(None, 2)
            if len(parts) >= 2:
                return f"exec {parts[1]}"
        return command

    def populate(self, query: str, launcher_core) -> None:
        """Populate launcher with keybindings."""
        self._reload_config()

        if not self.bindings:
            launcher_core.add_launcher_result(
                "Failed to load keybindings", "Check scroll config file", index=1
            )
            return

        query = query.lower()
        results = []

        # First add default mode bindings (no header)
        default_bindings = self.bindings.get("", [])
        if default_bindings:
            for binding in default_bindings:
                if self._matches_query(binding, query):
                    results.append((binding, ""))  # Empty mode string for default

        # Then add mode bindings with headers
        mode_order = sorted(self.bindings.keys())
        for mode in mode_order:
            if not mode:  # Skip default mode (already added)
                continue
            mode_bindings = self.bindings.get(mode, [])
            if not mode_bindings:
                continue

            # Check if any binding in this mode matches
            mode_has_matches = any(self._matches_query(b, query) for b in mode_bindings)

            if not query or mode_has_matches:
                # Add mode separator
                results.append((None, f"=== Mode: {mode} ==="))

                # Add bindings for this mode
                for binding in mode_bindings:
                    if not query or self._matches_query(binding, query):
                        results.append((binding, mode))

        # Display results
        index = 1
        for binding, mode_display in results:
            if binding is None:
                # This is a mode separator
                launcher_core.add_launcher_result(
                    mode_display, "", index=None, action_data=None
                )
            else:
                # This is a binding
                launcher_core.add_launcher_result(
                    binding.keys,
                    self._extract_meaningful_command(binding.meaningful_command),
                    index=index if index <= 9 else None,
                    action_data={"type": "keybinding", "binding": binding},
                )
                index += 1

        launcher_core.current_apps = []

    def _matches_query(self, binding: Keybinding, query: str) -> bool:
        """Check if binding matches the search query."""
        if not query:
            return True

        search_text = f"{binding.keys} {binding.command} {binding.mode}".lower()
        return query in search_text
