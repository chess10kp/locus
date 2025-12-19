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
    # Import here to avoid circular imports
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.config import LAUNCHER_CONFIG

    cache_config = LAUNCHER_CONFIG["cache"]
    cache_dir = Path(cache_config["cache_dir"]).expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / cache_config["apps_cache_file"]


def is_cache_valid(cache_path):
    """Check if the cache is valid (exists and not too old)."""
    # Import here to avoid circular imports
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.config import LAUNCHER_CONFIG

    if not LAUNCHER_CONFIG["performance"]["enable_cache"]:
        return False

    if not cache_path.exists():
        return False

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        # Check basic structure
        if (
            not isinstance(cache_data, dict)
            or "timestamp" not in cache_data
            or "apps" not in cache_data
        ):
            return False

        cache_time = datetime.fromisoformat(cache_data.get("timestamp", ""))

        max_age_hours = LAUNCHER_CONFIG["performance"]["cache_max_age_hours"]
        age = datetime.now() - cache_time

        # Check if cache is too old
        if age >= timedelta(hours=max_age_hours):
            return False

        # Basic validation of apps data
        apps = cache_data.get("apps", [])
        if not isinstance(apps, list):
            return False

        # Check if we have at least some apps (cache should not be empty unless no apps exist)
        if len(apps) == 0:
            # Empty cache might be valid if no apps were found
            return True

        # Validate a few sample apps to ensure cache integrity
        sample_size = min(5, len(apps))
        for i in range(sample_size):
            app = apps[i]
            if not isinstance(app, dict) or "name" not in app or "file" not in app:
                return False

        return True

    except (json.JSONDecodeError, KeyError, ValueError, OSError, TypeError):
        return False

    if not cache_path.exists():
        return False

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        cache_time = datetime.fromisoformat(cache_data.get("timestamp", ""))
        max_age_hours = LAUNCHER_CONFIG["performance"]["cache_max_age_hours"]
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
        with open(cache_path, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
        return cache_data.get("apps", [])
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def save_apps_cache(apps):
    """Save apps to cache with timestamp."""
    cache_path = get_apps_cache_path()

    cache_data = {"timestamp": datetime.now().isoformat(), "apps": apps}

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
    except OSError:
        pass  # Fail silently if we can't write cache


def _scan_directory(dir_path, debug_print=False, timeout=None):
    """Scan a single directory for desktop files. Returns list of apps."""
    import time

    start_time = time.time()

    apps = []
    if dir_path.exists():
        if debug_print:
            print(f"Checking dir: {dir_path}")
        count = 0
        try:
            for desktop_file in dir_path.glob("*.desktop"):
                # Check timeout if specified
                if timeout and (time.time() - start_time) > timeout:
                    if debug_print:
                        print(
                            f"Timeout reached for {dir_path}, scanned {count} apps so far"
                        )
                    break

                app = parse_desktop_file(desktop_file)
                if app:
                    apps.append(app)
                    count += 1
        except (OSError, PermissionError) as e:
            if debug_print:
                print(f"Error scanning {dir_path}: {e}")
        if debug_print:
            print(f"Loaded {count} apps from {dir_path}")
    return apps


def load_desktop_apps(force_refresh=False):
    """Load desktop applications, using cache if available."""
    # Import here to avoid circular imports
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.config import LAUNCHER_CONFIG

    # First, try to load from cache
    if not force_refresh and LAUNCHER_CONFIG["performance"]["enable_cache"]:
        cached_apps = load_apps_cache()
        if cached_apps:
            if LAUNCHER_CONFIG["advanced"]["debug_print"]:
                print(f"Loaded {len(cached_apps)} apps from cache")
            return cached_apps

    # If no valid cache, load from disk
    apps = []
    dirs = []
    desktop_config = LAUNCHER_CONFIG["desktop_apps"]

    # XDG_DATA_HOME/applications
    if desktop_config["scan_user_dir"]:
        xdg_data_home = os.environ.get("XDG_DATA_HOME", "~/.local/share")
        dirs.append(Path(xdg_data_home).expanduser() / "applications")

    # XDG_DATA_DIRS/applications
    if desktop_config["scan_system_dirs"]:
        xdg_data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
        for data_dir in xdg_data_dirs.split(":"):
            dirs.append(Path(data_dir) / "applications")

    # Additional common locations
    if desktop_config["scan_flatpak"]:
        dirs.append(Path("/var/lib/flatpak/exports/share/applications"))

    # Add /opt/*/share/applications
    if desktop_config["scan_opt_dirs"]:
        for opt_path in glob.glob("/opt/*/share/applications"):
            dirs.append(Path(opt_path))

    # Add snap desktop applications
    if desktop_config["scan_snap"]:
        snap_dir = Path("/var/lib/snapd/desktop/applications")
        if snap_dir.exists():
            dirs.append(snap_dir)

    # Add custom directories
    for custom_dir in desktop_config["custom_dirs"]:
        dirs.append(Path(custom_dir).expanduser())

    debug_print = LAUNCHER_CONFIG["advanced"]["debug_print"]
    max_scan_time = desktop_config.get("max_scan_time", 5.0)

    # Check if parallel scanning is enabled
    if LAUNCHER_CONFIG["performance"]["enable_parallel_scanning"]:
        # Use parallel scanning for better performance
        import concurrent.futures

        # Calculate timeout per directory (distribute total time among directories)
        dir_timeout = max_scan_time / len(dirs) if dirs else max_scan_time

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(dirs), 8)
        ) as executor:
            # Submit all directory scans with timeout
            future_to_dir = {
                executor.submit(
                    _scan_directory, dir_path, debug_print, dir_timeout
                ): dir_path
                for dir_path in dirs
            }

            # Collect results as they complete, with overall timeout
            try:
                for future in concurrent.futures.as_completed(
                    future_to_dir, timeout=max_scan_time
                ):
                    dir_apps = future.result()
                    apps.extend(dir_apps)
            except concurrent.futures.TimeoutError:
                if debug_print:
                    print(f"Overall scanning timeout reached after {max_scan_time}s")
                # Cancel remaining tasks
                for future in future_to_dir:
                    future.cancel()
    else:
        # Use sequential scanning for GTK compatibility
        import time

        start_time = time.time()

        for dir_path in dirs:
            # Check if we've exceeded the timeout
            if time.time() - start_time > max_scan_time:
                if debug_print:
                    print(f"Scanning timeout reached after {max_scan_time}s")
                break

            dir_apps = _scan_directory(dir_path, debug_print, max_scan_time)
            apps.extend(dir_apps)

    # Process apps
    if LAUNCHER_CONFIG["advanced"]["deduplicate_apps"]:
        # Remove duplicate apps based on executable name
        seen_execs = set()
        unique_apps = []
        for app in apps:
            exec_name = app.get("exec", "")
            if exec_name and exec_name not in seen_execs:
                seen_execs.add(exec_name)
                unique_apps.append(app)
        apps = unique_apps

    # Sort apps
    if LAUNCHER_CONFIG["advanced"]["sort_apps_alphabetically"]:
        apps = sorted(apps, key=lambda x: x["name"].lower())

    if LAUNCHER_CONFIG["advanced"]["debug_print"]:
        print(f"Total loaded {len(apps)} apps")

    # Save to cache if enabled
    if LAUNCHER_CONFIG["performance"]["enable_cache"]:
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
    # Import here to avoid circular imports
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.config import LAUNCHER_CONFIG

    try:
        # Fast pre-check: read first few lines to check for [Desktop Entry]
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            header = f.read(1024)  # Read first 1KB
            if "[Desktop Entry]" not in header:
                return None

        config = configparser.ConfigParser(interpolation=None)
        config.read(file_path, encoding="utf-8")

        if not config.has_section("Desktop Entry"):
            return None
        entry = config["Desktop Entry"]

        # Skip hidden apps unless explicitly requested
        if not LAUNCHER_CONFIG["search"]["show_hidden_apps"]:
            if entry.get("NoDisplay", "false").lower() == "true":
                return None
            if entry.get("Hidden", "false").lower() == "true":
                return None

        name = entry.get("Name")
        exec_cmd = entry.get("Exec")
        if not name or not exec_cmd:
            return None

        # Validate desktop file format if enabled
        if LAUNCHER_CONFIG["advanced"]["validate_desktop_files"]:
            # Basic validation
            if not isinstance(name, str) or not isinstance(exec_cmd, str):
                return None

        return {
            "name": name,
            "exec": exec_cmd.split()[0],  # Take first part
            "icon": entry.get("Icon", ""),
            "file": str(file_path),
        }
    except Exception as e:
        if LAUNCHER_CONFIG["advanced"]["debug_print"]:
            print(f"Error parsing {file_path}: {e}")
        return None
