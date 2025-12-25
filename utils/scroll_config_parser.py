# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import os
import re


@dataclass
class Keybinding:
    keys: str  # e.g., "Mod4+Return" (variables expanded)
    command: str  # Full command
    meaningful_command: str  # Clean/meaningful part
    mode: str  # Mode name (empty string = default mode)
    flags: List[str]  # e.g., ["--no-repeat", "--locked"]
    raw_line: str  # Original line


class ScrollConfigParser:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._detect_config_path()
        self.variables: Dict[str, str] = {}
        self.bindings: Dict[str, List[Keybinding]] = {"": []}  # "" = default mode

    def parse(self) -> Dict[str, List[Keybinding]]:
        """Parse config and return bindings grouped by mode."""
        try:
            with open(self.config_path, "r") as f:
                lines = self._read_continued_lines(f)

            self._parse_lines(lines)
            self._expand_all_variables()
            return self.bindings
        except Exception:
            # Return empty bindings on error
            return {"": []}

    def _detect_config_path(self) -> str:
        """Find scroll config file in standard locations."""
        paths = [
            os.path.expanduser("~/.config/scroll/config"),
            os.path.expanduser("~/.scroll/config"),
            "/etc/scroll/config",
            # Fallback to i3 paths
            os.path.expanduser("~/.config/i3/config"),
            os.path.expanduser("~/.i3/config"),
            "/etc/i3/config",
        ]
        for path in paths:
            if os.path.exists(path):
                return path
        raise FileNotFoundError("No scroll config found")

    def _read_continued_lines(self, file_obj) -> List[str]:
        """Read file, handling line continuation with backslash."""
        lines = []
        continued_line = ""
        for line in file_obj:
            line = line.rstrip()
            if line.endswith("\\"):
                continued_line += line[:-1] + " "
            else:
                lines.append(continued_line + line)
                continued_line = ""
        return lines

    def _parse_lines(self, lines: List[str]):
        """Parse config lines, tracking mode context and variables."""
        current_mode = ""
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                i += 1
                continue

            # Track variable definitions
            if line.startswith("set "):
                self._parse_variable(line)
                i += 1
                continue

            # Handle mode blocks
            mode_match = re.match(r'^mode\s+"([^"]+)"\s*\{', line)
            if mode_match:
                mode_name = mode_match.group(1)
                if mode_name not in self.bindings:
                    self.bindings[mode_name] = []
                self._parse_mode_block(lines, i, mode_name)
                i = self._find_matching_brace(lines, i) + 1
                continue

            # Handle multiline bindsym blocks: bindsym { ... }
            bindsym_block_match = re.match(r"^\s*(?:bind(?:code|sym))\s*\{", line)
            if bindsym_block_match:
                self._parse_multiline_bindsym_block(lines, i, current_mode)
                i = self._find_matching_brace(lines, i) + 1
                continue

            # Handle simple bindsym/bindcode
            bindsym_match = re.match(r"^\s*(bind(?:code|sym))\s+(.+)", line)
            if bindsym_match:
                binding = self._parse_bindsym(line, current_mode)
                if binding:
                    if binding.mode not in self.bindings:
                        self.bindings[binding.mode] = []
                    self.bindings[binding.mode].append(binding)

            i += 1

    def _parse_variable(self, line: str):
        """Parse 'set $var value' statement."""
        match = re.match(r"^set\s+\$(\w+)\s+(.+)$", line)
        if match:
            var_name = match.group(1)
            var_value = match.group(2).strip()
            self.variables[var_name] = var_value

    def _parse_mode_block(self, lines: List[str], start_idx: int, mode_name: str):
        """Parse contents of a mode block."""
        end_idx = self._find_matching_brace(lines, start_idx)
        for i in range(start_idx + 1, end_idx):
            line = lines[i].strip()
            if not line or line.startswith("#"):
                continue
            bindsym_match = re.match(r"^\s*(bind(?:code|sym))\s+(.+)", line)
            if bindsym_match:
                binding = self._parse_bindsym(line, mode_name)
                if binding:
                    if mode_name not in self.bindings:
                        self.bindings[mode_name] = []
                    self.bindings[mode_name].append(binding)

    def _parse_multiline_bindsym_block(
        self, lines: List[str], start_idx: int, mode: str
    ):
        """Parse special bindsym { ... } block syntax."""
        end_idx = self._find_matching_brace(lines, start_idx)
        for i in range(start_idx + 1, end_idx):
            line = lines[i].strip()
            if not line or line.startswith("#"):
                continue
            binding = self._parse_bindsym(line, mode)
            if binding:
                if mode not in self.bindings:
                    self.bindings[mode] = []
                self.bindings[mode].append(binding)

    def _find_matching_brace(self, lines: List[str], start_idx: int) -> int:
        """Find closing brace matching opening brace at start_idx."""
        depth = 1
        i = start_idx + 1
        while i < len(lines) and depth > 0:
            line = lines[i]
            depth += line.count("{")
            depth -= line.count("}")
            i += 1
        return i - 1

    def _parse_bindsym(self, line: str, mode: str) -> Optional[Keybinding]:
        """Parse a single bindsym/bindcode line."""
        parts = line.split(None, 1)  # Split on first whitespace
        if len(parts) < 2:
            return None

        command_type = parts[0]  # "bindsym" or "bindcode"
        rest = parts[1].strip()

        # Parse flags before key combo
        flags = []
        while rest.startswith("--"):
            flag_end = rest.find(" ", 1)
            if flag_end == -1:
                break
            flags.append(rest[:flag_end])
            rest = rest[flag_end + 1 :].strip()

        # Split at first word that's not part of the key combo
        # Key combo ends at the first word that's not a modifier/key
        words = rest.split()
        if not words:
            return None

        # Find where the key combo ends and command begins
        key_combo = ""
        command = ""
        command_start_idx = -1

        for i, word in enumerate(words):
            # Check if this word starts a command (not a key/modifier)
            if word in [
                "exec",
                "mode",
                "focus",
                "move",
                "resize",
                "kill",
                "fullscreen",
                "floating",
                "workspace",
                "layout",
                "scratchpad",
                "gaps",
                "opacity",
                "border",
                "mark",
                "unmark",
                "split",
                "sticky",
                "inhibit_idle",
                "nop",
                "jump",
                "cycle_size",
                "fit_size",
                "align",
                "animations_enable",
                "exit",
                "reload",
                "restart",
                "input",
                "output",
                "bar",
                "assign",
                "for_window",
                "hide_edge_borders",
                "smart_borders",
                "smart_gaps",
                "title_align",
                "include",
                "client",
                "font",
                "default_border",
                "default_floating_border",
                "hide_cursor",
                "seat",
                "xwayland",
            ]:
                command_start_idx = i
                break

        if command_start_idx == -1:
            # No recognized command found, skip this line
            return None

        key_combo = " ".join(words[:command_start_idx])
        command = " ".join(words[command_start_idx:])

        meaningful_command = self._extract_meaningful_command(command)
        return Keybinding(
            keys=key_combo,
            command=command,
            meaningful_command=meaningful_command,
            mode=mode,
            flags=flags,
            raw_line=line,
        )

    def _extract_meaningful_command(self, command: str) -> str:
        """Extract the meaningful part of a command."""
        # Remove chained commands separated by ; or , (keep only first)
        for sep in [";", ","]:
            if sep in command:
                command = command.split(sep)[0].strip()

        # Remove trailing mode commands
        command = re.sub(r'\s+mode\s+"[^"]+"\s*$', "", command)
        command = re.sub(r"\s+mode\s+default\s*$", "", command)

        # For exec commands, just show the executable part
        if command.startswith("exec "):
            cmd = command[5:].strip()
            # Remove pipes and && chains
            if " | " in cmd or " && " in cmd:
                cmd = cmd.split(" | ")[0].split(" && ")[0].strip()
            # Show just the command name
            parts = cmd.split(None, 1)
            cmd = parts[0]
            return f"exec {cmd}"

        return command.strip()

    def _expand_all_variables(self):
        """Expand $variables in all keybindings."""
        for mode_bindings in self.bindings.values():
            for binding in mode_bindings:
                binding.keys = self._expand_variables(binding.keys)
                binding.command = self._expand_variables(binding.command)
                # Re-extract meaningful command from expanded command
                binding.meaningful_command = self._extract_meaningful_command(
                    binding.command
                )
                binding.meaningful_command = self._expand_variables(
                    binding.meaningful_command
                )

    def _expand_variables(self, text: str) -> str:
        """Expand variable references in text (but not $$var)."""
        # Sort variables by length (longest first) to avoid partial replacements
        sorted_vars = sorted(
            self.variables.items(), key=lambda x: len(x[0]), reverse=True
        )

        def replace_var(match):
            var_name = match.group(1)
            if var_name in self.variables:
                return self.variables[var_name]
            return match.group(0)  # Keep original if not found

        # Replace $var but not $$var
        pattern = r"(?<!\$)\$(\w+)"
        return re.sub(pattern, replace_var, text)
