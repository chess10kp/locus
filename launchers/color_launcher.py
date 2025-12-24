# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import os
import subprocess
import json
import re
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from gi.repository import GdkPixbuf, GLib
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode

logger = logging.getLogger("ColorLauncher")


class ColorHook(LauncherHook):
    def __init__(self, color_launcher):
        self.color_launcher = color_launcher

    def on_select(self, launcher, item_data) -> bool:
        """Handle color selection - copy hex to clipboard"""
        if launcher.active_launcher_context != "color":
            return False

        # Handle color hex values
        if isinstance(item_data, str) and item_data.startswith("#"):
            self.color_launcher.copy_to_clipboard(item_data)
            return True

        # Handle "Pick Color" command
        if isinstance(item_data, str) and item_data == "Pick Color":
            # Hide launcher first, then pick color asynchronously
            if self.color_launcher.launcher:
                self.color_launcher.launcher.hide()
            # Use idle_add to defer the color picking so hide takes effect
            from gi.repository import GLib

            GLib.idle_add(self.color_launcher._do_pick_color_async)
            return True

        return False

    def on_enter(self, launcher, text: str) -> bool:
        """Handle enter key"""
        if text.startswith(">color") and len(text) > 6:
            action = text[6:].strip()
            if action in ["pick", ""]:
                self.color_launcher.pick_color()
                return True
        return False

    def on_tab(self, launcher, text: str) -> Optional[str]:
        """Handle tab completion for 'pick' command"""
        if text.startswith(">color"):
            rest = text[6:].strip()
            if rest.startswith("pi"):
                return ">color pick"
        return None


class ColorLauncher(LauncherInterface):
    @classmethod
    def check_dependencies(cls) -> tuple[bool, str]:
        """Check if required dependencies are available."""
        from utils.deps import check_command_exists

        required = ["grim", "slurp", "convert", "wl-copy"]
        missing = [cmd for cmd in required if not check_command_exists(cmd)]

        if missing:
            return False, f"Missing dependencies: {', '.join(missing)}"
        return True, ""

    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.color_history: List[Dict[str, Any]] = []
        self.history_file = Path.home() / ".cache" / "locus" / "color_history.json"
        self.hook = ColorHook(self)

        # Ensure cache directory exists
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing color history
        self._load_color_history()

        # Register hook
        if main_launcher and hasattr(main_launcher, "hook_registry"):
            main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self):
        return ["color", "cpicker"]

    @property
    def name(self):
        return "color"

    def get_size_mode(self):
        return LauncherSizeMode.DEFAULT, None

    def get_grid_config(self):
        return None

    def populate(self, query: str, launcher_core):
        """Populate the launcher with color history or pick action."""
        query = query.strip().lower()

        # Handle "pick" command
        if query == "pick":
            launcher_core.add_launcher_result(
                title="Pick Color",
                subtitle="Click to select a color from screen",
                action_data="Pick Color",
                icon_name="color-picker",
            )
            launcher_core.current_apps = []
            return

        # Default view: show color history
        if not self.color_history:
            launcher_core.add_launcher_result(
                title="No colors yet",
                subtitle="Type 'pick' to select a color",
                icon_name="image-missing",
            )
        else:
            # Display color history (most recent first)
            for i, color_entry in enumerate(self.color_history[:10]):
                hex_color = color_entry["hex"]
                pixbuf = self._create_color_pixbuf(hex_color, 32, 32)

                launcher_core.add_launcher_result(
                    title=hex_color.upper(),
                    subtitle=f"Color {i + 1}",
                    action_data=hex_color,
                    icon_name=None,  # Use pixbuf instead
                )

        # Add "Pick Color" button at the end
        launcher_core.add_launcher_result(
            title="Pick New Color",
            subtitle="Select color from screen",
            action_data="Pick Color",
            icon_name="color-picker",
        )

        launcher_core.current_apps = []

    def pick_color(self):
        """Pick a color from the screen using grim+slurp+convert."""
        # This method is kept for backward compatibility
        self._do_pick_color_async()

    def _do_pick_color_async(self):
        """Pick a color from the screen using grim+slurp+convert (async)."""
        try:
            # Clean environment for child processes
            env = dict(os.environ.items())
            env.pop("LD_PRELOAD", None)

            # Run the color picking command
            cmd = "grim -g \"$(slurp -p)\" -t ppm - | convert - -format '%[pixel:p{0,0}]' txt:- | tail -n 1 | cut -d ' ' -f 4"
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True,
                env=env,
            )

            if result.returncode == 0 and result.stdout.strip():
                # Parse the color (format: "srgb(255,0,0)" or "#ff0000")
                color_str = result.stdout.strip()
                hex_color = self._parse_color_to_hex(color_str)

                if hex_color:
                    # Add to history
                    self._add_color_to_history(hex_color)

                    # Copy to clipboard
                    self.copy_to_clipboard(hex_color)

                    # Show launcher again to display updated history
                    self._show_launcher_centered()
                else:
                    self._show_error(f"Could not parse color: {color_str}")
                    self._show_launcher_centered()
            else:
                self._show_error("Color picking cancelled or failed")
                self._show_launcher_centered()

        except Exception as e:
            self._show_error(f"Error picking color: {e}")
            self._show_launcher_centered()

        except Exception as e:
            self._show_error(f"Error picking color: {e}")
            # Show launcher again on error
            if self.launcher:
                self.launcher.show_launcher()

    def _parse_color_to_hex(self, color_str: str) -> Optional[str]:
        """Parse various color formats to hex string."""
        color_str = color_str.strip()

        # Already in hex format
        if re.match(r"^#?[0-9a-fA-F]{3,6}$", color_str):
            if not color_str.startswith("#"):
                color_str = "#" + color_str
            # Expand 3-digit hex to 6-digit
            if len(color_str) == 4:  # #rgb
                r, g, b = color_str[1], color_str[2], color_str[3]
                return f"#{r}{r}{g}{g}{b}{b}"
            return color_str.lower()

        # srgb(r,g,b) format
        match = re.match(r"srgb\((\d+),(\d+),(\d+)\)", color_str)
        if match:
            r, g, b = map(int, match.groups())
            return f"#{r:02x}{g:02x}{b:02x}"

        # rgb(r,g,b) format
        match = re.match(r"rgb\((\d+),(\d+),(\d+)\)", color_str)
        if match:
            r, g, b = map(int, match.groups())
            return f"#{r:02x}{g:02x}{b:02x}"

        return None

    def _create_color_pixbuf(
        self, hex_color: str, width: int, height: int
    ) -> GdkPixbuf.Pixbuf:
        """Create a solid color pixbuf from hex color string using Cairo."""
        import cairo

        # Parse hex to RGB
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join([c * 2 for c in hex_color])

        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        # Create a Cairo image surface
        surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
        ctx = cairo.Context(surface)

        # Set source color and paint (Cairo uses 0-1 range)
        ctx.set_source_rgb(r / 255.0, g / 255.0, b / 255.0)
        ctx.paint()

        # Convert to GdkPixbuf
        # Get the surface data
        data = surface.get_data()
        stride = surface.get_stride()

        # Create pixbuf from the surface data
        pixbuf = GdkPixbuf.Pixbuf.new_from_data(
            data,
            GdkPixbuf.Colorspace.RGB,
            True,  # has_alpha
            8,  # bits_per_sample
            width,
            height,
            stride,
        )

        return pixbuf

    def _add_color_to_history(self, hex_color: str):
        """Add a color to history, maintaining max 10 colors."""
        import time

        # Check if color already exists (most recent occurrence)
        for entry in self.color_history:
            if entry["hex"].lower() == hex_color.lower():
                # Move to front
                self.color_history.remove(entry)
                break

        # Add new color at beginning
        self.color_history.insert(
            0,
            {
                "hex": hex_color.lower(),
                "timestamp": time.time(),
            },
        )

        # Trim to 10 colors
        self.color_history = self.color_history[:10]

        # Save to disk
        self._save_color_history()

    def _load_color_history(self):
        """Load color history from cache file."""
        try:
            if self.history_file.exists():
                with open(self.history_file, "r") as f:
                    data = json.load(f)
                    self.color_history = data.get("colors", [])
        except Exception as e:
            logger.warning(f"Error loading color history: {e}")
            self.color_history = []

    def _save_color_history(self):
        """Save color history to cache file."""
        try:
            data = {
                "colors": self.color_history,
                "version": 1,
            }
            with open(self.history_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Error saving color history: {e}")

    def copy_to_clipboard(self, text: str):
        """Copy text to clipboard using wl-copy or xclip."""
        try:
            env = dict(os.environ.items())
            env.pop("LD_PRELOAD", None)

            # Try wl-copy first (Wayland)
            try:
                subprocess.run(["wl-copy"], input=text.encode(), check=True, env=env)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback to xclip (X11)
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text.encode(),
                    check=True,
                    env=env,
                )

            # Show status message
            from utils import send_status_message

            send_status_message(f"Copied {text} to clipboard")

        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")

        # Don't hide launcher here - let pick_color handle hide/show

    def _show_error(self, message: str):
        """Show error message to user."""
        from utils import send_status_message

        send_status_message(f"Color picker: {message}")

    def _show_launcher_centered(self):
        """Show the launcher (GTK will preserve positioning)."""
        if self.launcher:
            self.launcher.present()

    def cleanup(self) -> None:
        """Clean up resources and save history."""
        self._save_color_history()
