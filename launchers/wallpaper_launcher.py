# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import os
import glob
import random
import re
import shutil
import subprocess
import hashlib
from pathlib import Path
from gi.repository import GdkPixbuf, Gtk
from core.hooks import LauncherHook
from core.launcher_registry import LauncherInterface, LauncherSizeMode
from typing import Optional


class WallpaperHook(LauncherHook):
    def __init__(self, launcher):
        self.launcher = launcher

    def on_select(self, launcher, item_data):
        """Handle button clicks for wallpaper selection and actions."""
        if not item_data:
            return False

        # Handle both string and dict input
        data_str = (
            item_data if isinstance(item_data, str) else str(item_data.get("", ""))
        )

        if data_str == "Set random wallpaper":
            self._set_random_wallpaper()
            launcher.hide()
            return True
        elif data_str == "Cycle wallpaper":
            self._cycle_wallpaper()
            launcher.hide()
            return True
        elif data_str.startswith(("No wallpapers found", "Wallpaper directory")):
            # Error messages, no action needed
            launcher.hide()
            return True
        else:
            # Individual wallpaper file
            self._set_wallpaper(data_str)
            launcher.hide()
            return True

        return False

    def on_enter(self, launcher, text):
        """Handle enter key for wallpaper operations."""
        # For now, no specific enter handling for wallpaper
        return False

    def on_tab(self, launcher, text):
        """Handle tab completion for wallpaper files and commands."""
        # Only handle wallpaper commands
        if not text.startswith(">wallpaper"):
            return None

        wp_dir = os.path.expanduser("~/Pictures/wp/")
        if not os.path.exists(wp_dir):
            return None

        # Check for special commands
        commands = ["Set random wallpaper", "Cycle wallpaper"]
        matching_commands = [
            cmd for cmd in commands if cmd.lower().startswith(text.lower())
        ]
        if matching_commands:
            return matching_commands[0]

        # Check for wallpaper files
        wallpapers = glob.glob(os.path.join(wp_dir, "*"))
        wallpapers = [os.path.basename(w) for w in wallpapers if os.path.isfile(w)]
        matching_wallpapers = [
            wp for wp in wallpapers if wp.lower().startswith(text.lower())
        ]

        if matching_wallpapers:
            return matching_wallpapers[0]

        return None

    def _set_random_wallpaper(self):
        """Set a random wallpaper."""
        wp_dir = os.path.expanduser("~/Pictures/wp/")
        wallpapers = glob.glob(os.path.join(wp_dir, "*"))
        wallpapers = [w for w in wallpapers if os.path.isfile(w)]
        if wallpapers:
            wp_path = random.choice(wallpapers)
            wp = os.path.basename(wp_path)
            self._set_wallpaper(wp)

    def _cycle_wallpaper(self):
        """Cycle to the next wallpaper in sequence."""
        wp_dir = os.path.expanduser("~/Pictures/wp/")
        default_link = os.path.join(wp_dir, "defaultwp.jpg")
        if os.path.islink(default_link):
            current = os.readlink(default_link)
            current_base = os.path.basename(current)
            match = re.match(r"(\D+)(\d+)\.(jpg|png)", current_base)
            if match:
                style = match.group(1)
                num = int(match.group(2))
                ext = match.group(3)
                num += 1
                next_file = f"{style}{num}.{ext}"
                next_path = os.path.join(wp_dir, next_file)
                if os.path.exists(next_path):
                    self._set_wallpaper(next_file)
                    return
                # Wrap to 1
                first_file = f"{style}1.{ext}"
                first_path = os.path.join(wp_dir, first_file)
                if os.path.exists(first_path):
                    self._set_wallpaper(first_file)
                    return
                # Try other ext
                alt_ext = "png" if ext == "jpg" else "jpg"
                alt_file = f"{style}1.{alt_ext}"
                alt_path = os.path.join(wp_dir, alt_file)
                if os.path.exists(alt_path):
                    self._set_wallpaper(alt_file)
                    return
        # Fallback to random
        self._set_random_wallpaper()

    def _get_walset(self):
        """Get wallpaper setter command."""
        # First, try to get from user config
        try:
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    "source ~/.config/scripts/configvars.sh && echo $walset",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                walset = result.stdout.strip()
                if walset:
                    return walset
        except Exception:
            pass

        # Auto-detect based on environment
        if os.environ.get("WAYLAND_DISPLAY"):
            if shutil.which("swaybg"):
                return "swaybg -i"
            elif shutil.which("swww"):
                return "swww img"
        elif os.environ.get("DISPLAY"):
            if shutil.which("feh"):
                return "feh --bg-scale"
            elif shutil.which("nitrogen"):
                return "nitrogen --set-scaled"

        return "swaybg -i"  # fallback

    def _set_wallpaper(self, wp):
        """Set a specific wallpaper."""
        wp_dir = os.path.expanduser("~/Pictures/wp/")
        wp_path = os.path.join(wp_dir, wp)
        default_link = os.path.join(wp_dir, "defaultwp.jpg")
        if os.path.exists(default_link) or os.path.islink(default_link):
            os.remove(default_link)
        os.symlink(wp_path, default_link)
        walset = self._get_walset()
        walset_parts = walset.split()
        if walset_parts[0] == "swaybg":
            # Kill existing swaybg
            try:
                result = subprocess.run(
                    ["pgrep", "swaybg"], capture_output=True, text=True
                )
                if result.returncode == 0:
                    pids = result.stdout.strip().split("\n")
                    for pid in pids:
                        subprocess.run(["kill", pid], check=False)
            except Exception:
                pass
        # Run the setter with the symlink path
        subprocess.Popen(walset_parts + [default_link])


class WallpaperLauncher(LauncherInterface):
    @classmethod
    def check_dependencies(cls) -> tuple[bool, str]:
        """Check if required dependencies are available.

        Returns:
            Tuple of (available, error_message)
        """
        from utils import check_file_exists

        wp_dir = check_file_exists("~/Pictures/wp/")
        if not wp_dir:
            return False, "Wallpaper directory ~/Pictures/wp/ not found"
        return True, ""

    def __init__(self, main_launcher=None):
        self.launcher = main_launcher
        self.cache_dir = Path.home() / ".cache" / "locus" / "wallpaper_thumbnails"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hook = WallpaperHook(self)

        # Register the hook with the main launcher if available
        if main_launcher and hasattr(main_launcher, "hook_registry"):
            main_launcher.hook_registry.register_hook(self.hook)

    @property
    def command_triggers(self):
        return ["wallpaper"]

    @property
    def name(self):
        return "wallpaper"

    def get_size_mode(self):
        return LauncherSizeMode.GRID, (1200, 800)

    def get_grid_config(self):
        return {
            "columns": 5,
            "item_width": 200,
            "item_height": 150,
            "spacing": 10,
            "show_metadata": False,
            "metadata_position": "hidden",
            "aspect_ratio": "original",
        }

    def handles_tab(self):
        return True

    def handle_tab(self, query: str, launcher_core) -> Optional[str]:
        """Handle tab completion for wallpaper files and commands."""
        wp_dir = os.path.expanduser("~/Pictures/wp/")
        if not os.path.exists(wp_dir):
            return None

        # Check for special commands
        commands = ["random", "cycle"]
        matching_commands = [
            cmd for cmd in commands if cmd.lower().startswith(query.lower())
        ]
        if matching_commands:
            return matching_commands[0]

        # Check for wallpaper files
        wallpapers = glob.glob(os.path.join(wp_dir, "*"))
        wallpapers = [os.path.basename(w) for w in wallpapers if os.path.isfile(w)]
        matching_wallpapers = [
            wp for wp in wallpapers if wp.lower().startswith(query.lower())
        ]

        if matching_wallpapers:
            return matching_wallpapers[0]

        return None

    def populate(self, query, launcher_core):
        wp_dir = os.path.expanduser("~/Pictures/wp/")
        if not os.path.exists(wp_dir):
            launcher_core.add_grid_result(
                title="Wallpaper directory not found",
                metadata={"error": "~/Pictures/wp/ not found"},
            )
            launcher_core.current_apps = []
            return

        # Handle special commands
        if query == "random":
            launcher_core.add_grid_result(
                title="Set Random Wallpaper",
                metadata={"action": "random"},
                action_data="Set random wallpaper",
            )
            launcher_core.current_apps = []
            return
        elif query == "cycle":
            launcher_core.add_grid_result(
                title="Cycle Wallpaper",
                metadata={"action": "cycle"},
                action_data="Cycle wallpaper",
            )
            launcher_core.current_apps = []
            return

        # Load and filter wallpapers
        wallpapers = glob.glob(os.path.join(wp_dir, "*"))
        wallpapers = [os.path.basename(w) for w in wallpapers if os.path.isfile(w)]

        # Filter by search term if provided (but still filter)
        if query:
            search_term = query.lower().strip()
            wallpapers = [wp for wp in wallpapers if search_term in wp.lower()]

        if not wallpapers:
            msg = (
                "No wallpapers found" if not query else f"No wallpapers match '{query}'"
            )
            launcher_core.add_grid_result(
                title=msg,
                metadata={"error": "No wallpapers found"},
            )
        else:
            # Display wallpapers as grid results (image-only)
            for i, wp in enumerate(sorted(wallpapers)[:25]):  # Show more in grid
                wp_path = os.path.join(wp_dir, wp)
                launcher_core.add_grid_result(
                    title=wp,
                    image_path=wp_path,
                    metadata={"filename": wp},
                    index=i + 1 if i < 9 else None,
                    action_data=wp,
                )

        launcher_core.current_apps = []

    def _get_cached_thumbnail_pixbuf(self, wp_path):
        """Get thumbnail pixbuf from cache or create and cache it."""
        cache_path = self.get_cache_path(wp_path)

        # Return cached pixbuf if it exists
        if cache_path.exists():
            try:
                return GdkPixbuf.Pixbuf.new_from_file(str(cache_path))
            except Exception:
                # Cache corrupted, regenerate
                pass

        # Generate new thumbnail
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(wp_path)
        aspect_ratio = pixbuf.get_width() / pixbuf.get_height()
        scaled_width = 200
        scaled_height = int(scaled_width / aspect_ratio)
        scaled_buf = pixbuf.scale_simple(
            scaled_width, scaled_height, GdkPixbuf.InterpType.BILINEAR
        )

        # Save to cache
        try:
            scaled_buf.savev(str(cache_path), "png", [], [])
        except Exception:
            pass  # Cache save failed, but we still have the pixbuf

        return scaled_buf

    def get_cache_path(self, wp_path):
        """Generate cache file path based on image file path and modification time."""
        file_stat = os.stat(wp_path)
        cache_key = f"{wp_path}_{file_stat.st_mtime}_{file_stat.st_size}"
        cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
        return self.cache_dir / f"{cache_hash}.png"

    def get_cached_thumbnail(self, wp_dir, wp):
        """Get thumbnail from cache or create and cache it."""
        wp_path = os.path.join(wp_dir, wp)
        cache_path = self.get_cache_path(wp_path)

        # Return cached thumbnail if it exists
        if cache_path.exists():
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(cache_path))
                image = Gtk.Image.new_from_pixbuf(pixbuf)
                image.set_size_request(200, -1)
                image.set_pixel_size(200)
                return image
            except Exception:
                # Cache corrupted, regenerate
                pass

        # Generate new thumbnail
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(wp_path)
        aspect_ratio = pixbuf.get_width() / pixbuf.get_height()
        scaled_width = 200
        scaled_height = int(scaled_width / aspect_ratio)
        scaled_buf = pixbuf.scale_simple(
            scaled_width, scaled_height, GdkPixbuf.InterpType.BILINEAR
        )

        # Save to cache
        try:
            scaled_buf.savev(str(cache_path), "png", [], [])
        except Exception:
            pass  # Cache save failed, but we still have the thumbnail

        image = Gtk.Image.new_from_pixbuf(scaled_buf)
        image.set_size_request(200, -1)
        image.set_pixel_size(200)
        return image

    def apply_wallpaper_button_style(self, button):
        """Apply larger button styling for wallpaper entries."""
        from utils import apply_styles

        apply_styles(
            button,
            """
            button {
                background: #3c3836;
                color: #ebdbb2;
                border: none;
                border-radius: 3px;
                padding: 15px;
                font-size: 14px;
                font-family: Iosevka;
                min-height: 220px;
            }
            button:hover {
                background: #504945;
            }
        """,
        )

    def on_wallpaper_clicked(self, button, wp):
        self.set_wallpaper(wp)
        if self.launcher:
            self.launcher.hide()

    def on_wallpaper_random(self, button):
        wp_dir = os.path.expanduser("~/Pictures/wp/")
        wallpapers = glob.glob(os.path.join(wp_dir, "*"))
        wallpapers = [w for w in wallpapers if os.path.isfile(w)]
        if wallpapers:
            wp_path = random.choice(wallpapers)
            wp = os.path.basename(wp_path)
            self.set_wallpaper(wp)
        if self.launcher:
            self.launcher.hide()

    def on_wallpaper_cycle(self, button):
        wp_dir = os.path.expanduser("~/Pictures/wp/")
        default_link = os.path.join(wp_dir, "defaultwp.jpg")
        if os.path.islink(default_link):
            current = os.readlink(default_link)
            current_base = os.path.basename(current)
            match = re.match(r"(\D+)(\d+)\.(jpg|png)", current_base)
            if match:
                style = match.group(1)
                num = int(match.group(2))
                ext = match.group(3)
                num += 1
                next_file = f"{style}{num}.{ext}"
                next_path = os.path.join(wp_dir, next_file)
                if os.path.exists(next_path):
                    self.set_wallpaper(next_file)
                    if self.launcher:
                        self.launcher.hide()
                    return
                # Wrap to 1
                first_file = f"{style}1.{ext}"
                first_path = os.path.join(wp_dir, first_file)
                if os.path.exists(first_path):
                    self.set_wallpaper(first_file)
                    if self.launcher:
                        self.launcher.hide()
                    return
                # Try other ext
                alt_ext = "png" if ext == "jpg" else "jpg"
                alt_file = f"{style}1.{alt_ext}"
                alt_path = os.path.join(wp_dir, alt_file)
                if os.path.exists(alt_path):
                    self.set_wallpaper(alt_file)
                    if self.launcher:
                        self.launcher.hide()
                    return
        # Fallback to random
        self.on_wallpaper_random(button)

    def get_walset(self):
        try:
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    "source ~/.config/scripts/configvars.sh && echo $walset",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                walset = result.stdout.strip()
                return walset if walset else "swaybg -i"
        except Exception:
            pass
        return "swaybg -i"  # default

    def set_wallpaper(self, wp):
        wp_dir = os.path.expanduser("~/Pictures/wp/")
        wp_path = os.path.join(wp_dir, wp)
        default_link = os.path.join(wp_dir, "defaultwp.jpg")
        if os.path.exists(default_link) or os.path.islink(default_link):
            os.remove(default_link)
        os.symlink(wp_path, default_link)
        walset = self.get_walset()
        walset_parts = walset.split()
        if walset_parts[0] == "swaybg":
            # Kill existing swaybg
            try:
                result = subprocess.run(
                    ["pgrep", "swaybg"], capture_output=True, text=True
                )
                if result.returncode == 0:
                    pids = result.stdout.strip().split("\n")
                    for pid in pids:
                        subprocess.run(["kill", pid], check=False)
            except Exception:
                pass
        # Run the setter with the symlink path
        subprocess.Popen(walset_parts + [default_link])
