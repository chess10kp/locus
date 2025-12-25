# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import os
import sys
import shlex
import logging
import time
import re
from typing import Optional, List, Dict

from gi.repository import GLib, Gio, GioUnix
from .config import CUSTOM_LAUNCHERS

logger = logging.getLogger("ProcessLauncher")


class PerformanceMonitor:
    """Track search performance statistics for optimization."""

    def __init__(self, window_size: int = 100):
        self.timings: List[Dict] = []
        self.window_size = window_size

    def record(
        self, operation: str, duration_ms: float, query: str = "", result_count: int = 0
    ):
        """Record a performance measurement."""
        self.timings.append(
            {
                "op": operation,
                "time": duration_ms,
                "query": query,
                "results": result_count,
                "ts": time.time(),
            }
        )

        # Keep only recent measurements
        if len(self.timings) > self.window_size:
            self.timings = self.timings[-self.window_size :]

    def get_stats(self) -> Dict:
        """Get performance statistics."""
        import statistics

        search_times = [t["time"] for t in self.timings if t["op"] == "search"]
        if not search_times:
            return {}

        return {
            "count": len(search_times),
            "mean": statistics.mean(search_times),
            "median": statistics.median(search_times),
            "p95": statistics.quantiles(search_times, n=20)[18]
            if len(search_times) > 20
            else max(search_times),
            "max": max(search_times),
            "min": min(search_times),
        }

    def get_slow_searches(self, threshold_ms: float = 50) -> List[Dict]:
        """Get searches that exceeded the threshold."""
        return [
            t for t in self.timings if t["op"] == "search" and t["time"] > threshold_ms
        ]


# --- GIO Compatibility Patching ---
try:
    SystemDesktopAppInfo = GioUnix.DesktopAppInfo
except (ImportError, AttributeError):
    SystemDesktopAppInfo = Gio.DesktopAppInfo

# Fix for older GLib versions where Unix streams might be moved
if not hasattr(Gio, "UnixInputStream") and "GioUnix" in sys.modules:
    from gi.repository import GioUnix

    Gio.UnixInputStream = getattr(GioUnix, "InputStream", None)
    Gio.UnixOutputStream = getattr(GioUnix, "OutputStream", None)


def detach_child() -> None:
    """
    Runs in the child process before execing.
    os.setsid() makes the child a session leader, detaching it from Python.
    """
    os.setsid()

    if not sys.stdout.isatty():
        with open(os.devnull, "w+b") as null_fp:
            null_fd = null_fp.fileno()
            for fp in [sys.stdin, sys.stdout, sys.stderr]:
                try:
                    os.dup2(null_fd, fp.fileno())
                except Exception:
                    pass


def launch_detached(cmd: List[str], working_dir: Optional[str] = None) -> None:
    """
    Spawns the process using GLib's async mechanism.
    """
    # Check for systemd-run (the cleanest way to launch on modern Linux)
    use_systemd_run = os.path.exists("/usr/bin/systemd-run")

    final_cmd = cmd
    if use_systemd_run:
        # systemd-run --user puts the app in its own independent cgroup
        final_cmd = ["systemd-run", "--user", "--scope", "--quiet"] + cmd

    # Sanitize Environment
    env = dict(os.environ.items())
    # Critical fix for Rider: Don't force GDK_BACKEND if we aren't sure
    if env.get("GDK_BACKEND") != "wayland":
        env.pop("GDK_BACKEND", None)

    # IMPORTANT: Remove LD_PRELOAD to prevent it from affecting child processes
    # The LD_PRELOAD is only needed for the status bar's layer-shell anchoring
    env.pop("LD_PRELOAD", None)

    try:
        envp = [f"{k}={v}" for k, v in env.items()]
        GLib.spawn_async(
            argv=final_cmd,
            envp=envp,
            flags=GLib.SpawnFlags.SEARCH_PATH_FROM_ENVP | GLib.SpawnFlags.SEARCH_PATH,
            child_setup=None if use_systemd_run else detach_child,
            **({"working_directory": working_dir} if working_dir else {}),
        )
        logger.info("Process spawned: %s", " ".join(final_cmd))
    except Exception as e:
        logger.exception('Could not launch "%s": %s', final_cmd, e)


class AppLauncher:
    @staticmethod
    def _find_desktop_file_by_name(app_name: str) -> Optional[str]:
        """
        Search for a desktop file by application name in standard directories.
        """
        from pathlib import Path

        # Convert app name to lowercase for case-insensitive matching
        app_name_lower = app_name.lower()

        desktop_dirs = [
            Path.home() / ".local" / "share" / "applications",
            Path("/usr/local/share/applications"),
            Path("/usr/share/applications"),
            Path("/var/lib/flatpak/exports/share/applications"),
            Path("/var/lib/snapd/desktop/applications"),
        ]

        for desktop_dir in desktop_dirs:
            if not desktop_dir.exists():
                continue

            exact_file = desktop_dir / f"{app_name_lower}.desktop"
            if exact_file.exists():
                return str(exact_file)

            try:
                for desktop_file in desktop_dir.glob("*.desktop"):
                    try:
                        # Try to load and check the desktop file name
                        app_info = SystemDesktopAppInfo.new_from_filename(
                            str(desktop_file)
                        )
                        if app_info:
                            file_name = app_info.get_name()
                            if file_name and file_name.lower() == app_name_lower:
                                return str(desktop_file)
                    except Exception:
                        # idk what we do here
                        continue
            except Exception:
                # Skip problematic directories
                continue

        return None

    @staticmethod
    def launch_by_desktop_file(
        desktop_file_path: str,
        project_path: Optional[str] = None,
        fallback_exec: Optional[str] = None,
        fallback_name: Optional[str] = None,
    ) -> bool:
        """
        Parses a .desktop file and launches the command within.
        Falls back to direct execution if desktop file is not available.
        """
        if desktop_file_path and os.path.exists(desktop_file_path):
            app_info = SystemDesktopAppInfo.new_from_filename(desktop_file_path)
            if app_info:
                app_exec = app_info.get_commandline()
                if app_exec:
                    app_exec = re.sub(r"\%[uUfFdDnNickvm]", "", app_exec).strip()
                    cmd = shlex.split(app_exec)
                    if project_path:
                        cmd.append(project_path)
                    working_dir = app_info.get_string("Path")
                    launch_detached(cmd, working_dir)
                    return True
                else:
                    logger.warning(
                        "Desktop file has no executable: %s", desktop_file_path
                    )
            else:
                logger.warning("Could not load desktop file: %s", desktop_file_path)
        else:
            logger.debug(
                "Desktop file path is empty or does not exist: %s", desktop_file_path
            )

        # Fallback: try to find desktop file by searching standard directories
        if fallback_name:
            found_desktop_file = AppLauncher._find_desktop_file_by_name(fallback_name)
            if found_desktop_file:
                logger.info(
                    "Found desktop file for %s: %s", fallback_name, found_desktop_file
                )
                return AppLauncher.launch_by_desktop_file(
                    found_desktop_file, project_path
                )

        if fallback_exec:
            logger.info("Launching %s directly as fallback", fallback_exec)
            cmd = [fallback_exec]
            if project_path:
                cmd.append(project_path)
            launch_detached(cmd)
            return True

        logger.error(
            "Could not launch application - no valid desktop file or executable found"
        )
        return False


BUILTIN_HANDLERS = {}


def register_builtin_handler(name: str, handler_func):
    """Register a builtin launcher handler function."""
    BUILTIN_HANDLERS[name] = handler_func


def handle_custom_launcher(
    command: str, apps: List[Dict], launcher_instance=None
) -> bool:
    """
    The main handler to bridge your configuration with the launcher.
    """
    # Debug logging
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"handle_custom_launcher called with command='{command}'")

    if command not in CUSTOM_LAUNCHERS:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Command '{command}' not in CUSTOM_LAUNCHERS")
        return False

    launcher = CUSTOM_LAUNCHERS[command]
    target_name = ""

    if isinstance(launcher, str):
        target_name = launcher
    elif isinstance(launcher, dict):
        launcher_type = launcher.get("type")
        if launcher_type == "app":
            target_name = launcher.get("name", "")
        elif launcher_type == "builtin":
            handler_name = launcher.get("handler")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Builtin handler '{handler_name}' requested")
            if handler_name and handler_name in BUILTIN_HANDLERS:
                # Call the builtin handler with the launcher instance
                if handler_name and handler_name in BUILTIN_HANDLERS:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Calling builtin handler '{handler_name}'")
                    # Call the builtin handler with the launcher instance
                    BUILTIN_HANDLERS[handler_name](launcher_instance)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Builtin handler '{handler_name}' completed")
                    return True
                return False
            else:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"No handler found for builtin '{handler_name}'")
                return False

    if target_name:
        for app in apps:
            if target_name.lower() in app["name"].lower():
                # 'app["file"]' should be the path to the .desktop file
                return AppLauncher.launch_by_desktop_file(app["file"])

    return False
