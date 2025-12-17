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
import subprocess
import hashlib
from pathlib import Path
from gi.repository import GdkPixbuf, Gtk


class WallpaperLauncher:
    def __init__(self, launcher):
        self.launcher = launcher
        self.cache_dir = Path.home() / ".cache" / "locus" / "wallpaper_thumbnails"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def populate(self, filter_text):
        wp_dir = os.path.expanduser("~/Pictures/wp/")
        if not os.path.exists(wp_dir):
            label_text = "Wallpaper directory ~/Pictures/wp/ not found"
            metadata = self.launcher.METADATA.get(label_text, "")
            button = self.launcher.create_button_with_metadata(label_text, metadata)
            self.launcher.list_box.append(button)
        elif filter_text == ">wallpaper random":
            metadata = self.launcher.METADATA.get("wallpaper", "")
            button = self.launcher.create_button_with_metadata(
                "Set random wallpaper", metadata
            )
            button.connect("clicked", self.on_wallpaper_random)
            self.launcher.list_box.append(button)
        elif filter_text == ">wallpaper cycle":
            metadata = self.launcher.METADATA.get("wallpaper", "")
            button = self.launcher.create_button_with_metadata(
                "Cycle wallpaper", metadata
            )
            button.connect("clicked", self.on_wallpaper_cycle)
            self.launcher.list_box.append(button)
        else:
            if not self.launcher.wallpaper_loaded:
                wallpapers = glob.glob(os.path.join(wp_dir, "*"))
                wallpapers = [
                    os.path.basename(w) for w in wallpapers if os.path.isfile(w)
                ]
                self.launcher.wallpaper_buttons = []
                for wp in sorted(wallpapers):
                    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
                    try:
                        image = self.get_cached_thumbnail(wp_dir, wp)
                        image.set_hexpand(False)
                        image.set_vexpand(False)
                    except Exception:
                        image = Gtk.Image()
                    metadata = self.launcher.METADATA.get(wp, "")
                    if metadata:
                        markup = f"{wp}\n<span size='smaller' color='#d5c4a1'>{metadata}</span>"
                        label = Gtk.Label()
                        label.set_markup(markup)
                        label.set_halign(Gtk.Align.START)
                        label.set_valign(Gtk.Align.START)
                        label.set_wrap(True)
                        label.set_wrap_mode(Gtk.WrapMode.WORD)
                        label.set_hexpand(True)
                        box.append(image)
                        box.append(label)
                    else:
                        label = Gtk.Label(label=wp)
                        label.set_halign(Gtk.Align.START)
                        label.set_hexpand(True)
                        box.append(image)
                        box.append(label)
                    button = Gtk.Button()
                    button.set_child(box)
                    button.get_child().set_halign(Gtk.Align.START)
                    button.connect("clicked", self.on_wallpaper_clicked, wp)
                    self.apply_wallpaper_button_style(button)
                    self.launcher.wallpaper_buttons.append((button, wp))
                self.launcher.wallpaper_loaded = True
            search_term = (
                filter_text[11:].strip().lower()
                if filter_text.startswith(">wallpaper ")
                else ""
            )
            matching = [
                (btn, wp)
                for btn, wp in self.launcher.wallpaper_buttons
                if not search_term or search_term in wp.lower()
            ]
            if not matching:
                msg = (
                    "No wallpapers found"
                    if not search_term
                    else f"No wallpapers match '{search_term}'"
                )
                metadata = self.launcher.METADATA.get(msg, "")
                button = self.launcher.create_button_with_metadata(msg, metadata)
                self.launcher.list_box.append(button)
            else:
                for btn, _ in matching:
                    self.launcher.list_box.append(btn)
        self.launcher.current_apps = []

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
        self.launcher.hide()

    def on_wallpaper_random(self, button):
        wp_dir = os.path.expanduser("~/Pictures/wp/")
        wallpapers = glob.glob(os.path.join(wp_dir, "*"))
        wallpapers = [w for w in wallpapers if os.path.isfile(w)]
        if wallpapers:
            wp_path = random.choice(wallpapers)
            wp = os.path.basename(wp_path)
            self.set_wallpaper(wp)
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
                    self.launcher.hide()
                    return
                # Wrap to 1
                first_file = f"{style}1.{ext}"
                first_path = os.path.join(wp_dir, first_file)
                if os.path.exists(first_path):
                    self.set_wallpaper(first_file)
                    self.launcher.hide()
                    return
                # Try other ext
                alt_ext = "png" if ext == "jpg" else "jpg"
                alt_file = f"{style}1.{alt_ext}"
                alt_path = os.path.join(wp_dir, alt_file)
                if os.path.exists(alt_path):
                    self.set_wallpaper(alt_file)
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
            subprocess.Popen(walset_parts + [wp_path])
        else:
            # For other setters like swww, use the symlink
            subprocess.Popen(walset_parts + [default_link])
