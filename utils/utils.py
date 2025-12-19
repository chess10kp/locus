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
import configparser
import glob
import socket
import json
import threading
from pathlib import Path
from datetime import datetime, timedelta

from gi.repository import Gtk, GLib  # pyright: ignore


def apply_styles(widget, css: str):
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode())
    context = widget.get_style_context()
    context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def send_status_message(message: str):
    """Send a message to update the status bar via IPC.

    Args:
        message: The message to display in the status bar
    """
    SOCKET_PATH = "/tmp/locus_socket"
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(1.0)  # 1 second timeout
        sock.connect(SOCKET_PATH)
        sock.sendall(message.encode("utf-8"))
        sock.close()
    except (OSError, socket.timeout):
        # Silently ignore IPC failures to avoid spam
        pass


def read_time() -> str:
    TIME_PATH = os.path.expanduser("~/.time")
    try:
        return open(TIME_PATH).read().strip()
    except FileNotFoundError:
        return "0"  # Default to 0 if file doesn't exist


async def is_running(process_name: str) -> bool:
    try:
        if not os.name == "nt":
            output = subprocess.check_output(["pgrep", process_name])
            return output.lower() != b""
    except subprocess.CalledProcessError:
        return False
    return False


def get_default_styling() -> str:
    import style

    return str(
        "  margin: %spx; margin-top: %spx; padding: %spx; border: %spx solid; border-radius: %spx; "
        % (
            style.WIDGET_MARGINS[0],
            style.WIDGET_MARGINS[0],
            style.PADDING,
            style.BORDER,
            style.BORDER_ROUNDING,
        ),
    )


def VBox(spacing: int = 6, hexpand: bool = False, vexpand: bool = False):
    return Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=spacing,
        hexpand=hexpand,
        vexpand=vexpand,
    )


def HBox(spacing: int = 6, hexpand: bool = False, vexpand: bool = False):
    return Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        spacing=spacing,
        hexpand=hexpand,
        vexpand=vexpand,
    )


# Cache for battery path to avoid repeated filesystem checks
_battery_path_cache = None


def get_battery_path() -> str | None:
    """Get the battery path, caching the result"""
    global _battery_path_cache
    if _battery_path_cache is not None:
        return _battery_path_cache

    # Try to get battery info from /sys/class/power_supply/
    battery_path = "/sys/class/power_supply/BAT0"  # Most common battery path
    if os.path.exists(battery_path):
        _battery_path_cache = battery_path
        return battery_path

    # Try alternative battery paths
    for i in range(10):
        alt_path = f"/sys/class/power_supply/BAT{i}"
        if os.path.exists(alt_path):
            _battery_path_cache = alt_path
            return alt_path

    _battery_path_cache = None
    return None


def get_battery_status() -> str:
    """Get battery percentage and charging status"""
    try:
        battery_path = get_battery_path()
        if battery_path is None:
            return "No Battery"

        # Read capacity and status in one go using subprocess for efficiency
        result = subprocess.run(
            ["cat", f"{battery_path}/capacity", f"{battery_path}/status"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                capacity = lines[0].strip()
                status = lines[1].strip()
                return f"{capacity} {status}"

        # Fallback to individual file reads if cat fails
        with open(f"{battery_path}/capacity", "r") as f:
            capacity = int(f.read().strip())
        with open(f"{battery_path}/status", "r") as f:
            status = f.read().strip()
        return f"{capacity} {status}"

    except (
        FileNotFoundError,
        ValueError,
        IOError,
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
    ):
        # Fallback to upower if available
        try:
            result = subprocess.run(
                ["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.split("\n")
                percentage = None
                state = None

                for line in lines:
                    if "percentage" in line.lower():
                        percentage = line.split(":")[-1].strip()
                    elif "state" in line.lower():
                        state = line.split(":")[-1].strip()

                if percentage and state:
                    return f"{percentage} {state}"
                elif percentage:
                    return percentage

            return "Battery Unknown"
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            return "No Battery"


def get_apps_cache_path():
    """Get the path to the desktop apps cache file."""
    cache_dir = Path.home() / ".cache" / "locus"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "desktop_apps.json"


def is_cache_valid(cache_path, max_age_hours=24):
    """Check if the cache is valid (exists and not too old)."""
    if not cache_path.exists():
        return False

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)

        cache_time = datetime.fromisoformat(cache_data.get('timestamp', ''))
        age = datetime.now() - cache_time
        return age < timedelta(hours=max_age_hours)
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        return False


def load_apps_cache():
    """Load apps from cache if valid."""
    cache_path = get_apps_cache_path()

    if not is_cache_valid(cache_path):
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        return cache_data.get('apps', [])
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def save_apps_cache(apps):
    """Save apps to cache with timestamp."""
    cache_path = get_apps_cache_path()

    cache_data = {
        'timestamp': datetime.now().isoformat(),
        'apps': apps
    }

    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2)
    except OSError:
        pass  # Fail silently if we can't write cache


def load_desktop_apps(force_refresh=False):
    """Load desktop applications, using cache if available."""
    # First, try to load from cache
    if not force_refresh:
        cached_apps = load_apps_cache()
        if cached_apps:
            print(f"Loaded {len(cached_apps)} apps from cache")
            return cached_apps

    # If no valid cache, load from disk
    apps = []
    dirs = []

    # XDG_DATA_HOME/applications
    xdg_data_home = os.environ.get("XDG_DATA_HOME", "~/.local/share")
    dirs.append(Path(xdg_data_home).expanduser() / "applications")

    # XDG_DATA_DIRS/applications
    xdg_data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    for data_dir in xdg_data_dirs.split(":"):
        dirs.append(Path(data_dir) / "applications")

    # Additional common locations
    dirs.append(Path("/var/lib/flatpak/exports/share/applications"))
    # Add /opt/*/share/applications
    for opt_path in glob.glob("/opt/*/share/applications"):
        dirs.append(Path(opt_path))
    # Add snap desktop applications
    snap_dir = Path("/var/lib/snapd/desktop/applications")
    if snap_dir.exists():
        dirs.append(snap_dir)

    for dir_path in dirs:
        if dir_path.exists():
            print(f"Checking dir: {dir_path}")
            count = 0
            for desktop_file in dir_path.glob("*.desktop"):
                app = parse_desktop_file(desktop_file)
                if app:
                    apps.append(app)
                    count += 1
            print(f"Loaded {count} apps from {dir_path}")

    # Sort and save to cache
    apps = sorted(apps, key=lambda x: x["name"].lower())
    print(f"Total loaded {len(apps)} apps")
    save_apps_cache(apps)
    return apps


def load_desktop_apps_background(callback=None):
    """Load desktop apps in background thread."""
    def load_in_thread():
        apps = load_desktop_apps(force_refresh=True)
        if callback:
            # Use GLib.idle_add to run callback in main thread
            GLib.idle_add(callback, apps)

    thread = threading.Thread(target=load_in_thread, daemon=True)
    thread.start()


def parse_desktop_file(file_path):
    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read(file_path, encoding="utf-8")
        if not config.has_section("Desktop Entry"):
            return None
        entry = config["Desktop Entry"]
        if entry.get("NoDisplay", "false").lower() == "true":
            return None
        if entry.get("Hidden", "false").lower() == "true":
            return None
        name = entry.get("Name")
        exec_cmd = entry.get("Exec")
        if not name or not exec_cmd:
            return None
        return {
            "name": name,
            "exec": exec_cmd.split()[0],  # Take first part
            "icon": entry.get("Icon", ""),
            "file": str(file_path),
        }
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None
