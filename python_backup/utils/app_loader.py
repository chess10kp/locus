# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

"""
High-performance app loading system using Gio.DesktopAppInfo directly.
Based on Ulauncher's approach for optimal performance.
"""

import threading
import logging
from pathlib import Path
from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta
import json

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib  # pyright: ignore
from .app_tracker import get_app_tracker
from .frecency_tracker import get_frecency_tracker

logger = logging.getLogger("AppLoader")


class DesktopAppInfo:
    """
    Wrapper around Gio.AppInfo for consistent interface.
    Mirrors Ulauncher's approach for cross-version compatibility.
    """

    def __init__(self, app_info: Gio.AppInfo):
        self._app_info = app_info
        self._name = None
        self._exec = None
        self._icon = None
        self._description = None
        self._keywords = []

    @property
    def name(self) -> str:
        """Get application name."""
        if self._name is None:
            self._name = self._app_info.get_name() or ""
        return self._name

    @property
    def executable(self) -> str:
        """Get executable name."""
        if self._exec is None:
            exec_line = self._app_info.get_commandline()
            if exec_line:
                # Take first part of command, remove field codes
                import re

                exec_line = re.sub(r"\%[uUfFdDnNickvm]", "", exec_line).strip()
                self._exec = exec_line.split()[0] if exec_line.split() else ""
            else:
                self._exec = ""
        return self._exec

    @property
    def icon_name(self) -> str:
        """Get icon name."""
        if self._icon is None:
            self._icon = self._app_info.get_icon()
            if self._icon:
                self._icon = (
                    self._icon.to_string()
                    if hasattr(self._icon, "to_string")
                    else str(self._icon)
                )
            else:
                self._icon = ""
        return self._icon or ""

    @property
    def description(self) -> str:
        """Get application description."""
        if self._description is None:
            self._description = self._app_info.get_description() or ""
        return self._description

    @property
    def keywords(self) -> List[str]:
        """Get application keywords."""
        if not self._keywords:
            keywords_str = self._app_info.get_keywords()
            if keywords_str:
                # Gio.DesktopAppInfo returns a string list, handle both string and list cases
                if isinstance(keywords_str, list):
                    self._keywords = keywords_str
                elif isinstance(keywords_str, str):
                    # Some versions return a semicolon-separated string
                    self._keywords = [
                        kw.strip() for kw in keywords_str.split(";") if kw.strip()
                    ]
                else:
                    self._keywords = []
            else:
                self._keywords = []
        return self._keywords

    @property
    def filename(self) -> str:
        """Get desktop file path."""
        return self._app_info.get_filename() or ""

    def should_show(self) -> bool:
        """Check if app should be shown in launcher."""
        return self._app_info.should_show()

    def to_dict(self) -> Dict:
        """Convert to dictionary format compatible with existing code."""
        return {
            "name": self.name,
            "exec": self.executable,
            "icon": self.icon_name,
            "file": self.filename,
            "description": self.description,
            "keywords": self.keywords,
        }


class FastAppLoader:
    """
    High-performance app loader using Gio.DesktopAppInfo directly.
    Mirrors Ulauncher's approach for optimal startup performance.
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "locus"
        self.cache_file = self.cache_dir / "apps_fast_cache.json"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._apps_cache: List[Dict] = []
        self._app_tracker = get_app_tracker()
        self._frecency_tracker = get_frecency_tracker()
        self._loading = False
        self._last_load_time = None

        # Performance settings
        self.cache_max_age_hours = 6  # Cache for 6 hours like Ulauncher
        self.enable_cache = True

    def is_cache_valid(self) -> bool:
        """Check if cache exists and is not too old."""
        if not self.enable_cache or not self.cache_file.exists():
            return False

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # Check cache structure
            if (
                not isinstance(cache_data, dict)
                or "apps" not in cache_data
                or "timestamp" not in cache_data
            ):
                return False

            # Check age
            cache_time = datetime.fromisoformat(cache_data["timestamp"])
            age = datetime.now() - cache_time
            return age < timedelta(hours=self.cache_max_age_hours)

        except (json.JSONDecodeError, ValueError, OSError):
            return False

    def save_cache(self, apps: List[Dict]):
        """Save apps to cache file."""
        if not self.enable_cache:
            return

        try:
            cache_data = {
                "apps": apps,
                "timestamp": datetime.now().isoformat(),
                "version": "2.0",
                "count": len(apps),
            }

            # Write to temp file first
            temp_file = self.cache_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2)

            temp_file.rename(self.cache_file)
            logger.debug(f"Saved {len(apps)} apps to cache")

        except OSError as e:
            logger.warning(f"Failed to save app cache: {e}")

    def load_cache(self) -> Optional[List[Dict]]:
        """Load apps from cache if valid."""
        if not self.is_cache_valid():
            return None

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            apps = cache_data.get("apps", [])
            logger.info(f"Loaded {len(apps)} apps from cache")
            return apps

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load app cache: {e}")
            return None

    def load_apps_from_system(self) -> List[Dict]:
        """
        Load apps using the most efficient method available.
        Try Gio.AppInfo first, fallback to desktop file scanning.
        """
        apps = []
        start_time = GLib.get_real_time() / 1000000  # Convert to seconds

        # Try to use Gio.AppInfo for direct system integration
        try:
            all_apps = Gio.AppInfo.get_all()
            logger.debug(f"Gio.AppInfo found {len(all_apps) if all_apps else 0} apps")

            if all_apps:
                for app_info in all_apps:
                    try:
                        # Skip apps that shouldn't be shown
                        if (
                            hasattr(app_info, "should_show")
                            and not app_info.should_show()
                        ):
                            continue

                        # Create basic app info
                        name = app_info.get_name() or ""
                        exec_line = app_info.get_commandline() or ""

                        # Only include apps with valid names and executables
                        if not name or not exec_line:
                            continue

                        # Clean up field codes from exec line
                        import re

                        exec_line = re.sub(r"\%[uUfFdDnNickvm]", "", exec_line).strip()
                        exec_name = exec_line.split()[0] if exec_line.split() else ""

                        app_dict = {
                            "name": name,
                            "exec": exec_name,
                            "icon": app_info.get_icon().to_string()
                            if app_info.get_icon()
                            else "",
                            "file": "",  # Gio.AppInfo doesn't provide filename
                            "description": app_info.get_description() or "",
                            "keywords": [],  # Keywords not easily accessible via Gio.AppInfo
                        }

                        logger.debug(
                            f"App '{name}': icon_name = '{app_dict.get('icon', 'NONE')}'"
                        )
                        apps.append(app_dict)

                    except Exception as e:
                        # Skip problematic apps but continue loading others
                        logger.debug(f"Skipping problematic app: {e}")
                        continue

            load_time = GLib.get_real_time() / 1000000 - start_time
            logger.info(f"Loaded {len(apps)} apps from Gio.AppInfo in {load_time:.3f}s")

            # Sort apps by name for consistent ordering
            apps.sort(key=lambda x: x["name"].lower())

            return apps

        except Exception as e:
            logger.warning(
                f"Gio.AppInfo failed ({e}), falling back to desktop file scanning"
            )
            # Fallback to the existing desktop file scanning method
            from utils.utils import load_desktop_apps

            return load_desktop_apps()

    def load_apps(self, force_refresh: bool = False) -> List[Dict]:
        """
        Load apps with caching support.
        Returns cached apps if available and fresh, otherwise loads from system.
        """
        if not force_refresh and not self._loading:
            # Try cache first
            cached_apps = self.load_cache()
            if cached_apps is not None:
                self._apps_cache = cached_apps
                self._last_load_time = datetime.now()
                return cached_apps

        # Load from system
        apps = self.load_apps_from_system()

        # Update cache
        self._apps_cache = apps
        self._last_load_time = datetime.now()
        self.save_cache(apps)

        return apps

    def load_apps_background(
        self, callback: Optional[Callable[[List[Dict]], None]] = None
    ):
        """Load apps in background thread."""
        if self._loading:
            return  # Already loading

        self._loading = True

        def load_in_thread():
            try:
                apps = self.load_apps(force_refresh=True)
                if callback:
                    # Use GLib.idle_add to run callback in main thread
                    GLib.idle_add(callback, apps)
            finally:
                self._loading = False

        thread = threading.Thread(target=load_in_thread, daemon=True)
        thread.start()

    def get_apps(self) -> List[Dict]:
        """Get currently loaded apps, loading if necessary."""
        if not self._apps_cache:
            return self.load_apps()
        return self._apps_cache

    def search_apps(
        self, query: str, max_results: int = 50, frecency_boost_factor: float = 0.3
    ) -> List[Dict]:
        """
        Search apps with frecency-based ranking.
        Uses the frecency tracker for intelligent ranking.
        """
        apps = self.get_apps()

        # Get frecency weights for all apps (normalized 0-1)
        frecency_weights = {}
        for app in apps:
            weight = self._frecency_tracker.get_normalized_weight(app["name"])
            frecency_weights[app["name"]] = weight

        if not query:
            # Return top apps by frecency if no query
            sorted_apps = sorted(
                apps, key=lambda x: frecency_weights.get(x["name"], 0.0), reverse=True
            )
            return sorted_apps[:max_results]

        # Use fuzzy search for query-based searches
        from utils.fuzzy_search import filter_apps_with_fuzzy

        # Get frequency weights for all apps (for backward compatibility)
        frequency_weights = {}
        for app in apps:
            weight = self._app_tracker.get_frequency_weight(app["name"])
            frequency_weights[app["name"]] = weight

        return filter_apps_with_fuzzy(
            query=query,
            apps=apps,
            frequency_weights=frequency_weights,
            frecency_weights=frecency_weights,
            max_results=max_results,
            frecency_boost_factor=frecency_boost_factor,
        )

    def track_app_launch(self, app_name: str):
        """Track an app launch for frequency and frecency ranking."""
        self._app_tracker.increment_app_start(app_name)
        self._frecency_tracker.increment(app_name)

    def get_stats(self) -> dict:
        """Get statistics about the app loader."""
        return {
            "cached_apps_count": len(self._apps_cache),
            "last_load_time": self._last_load_time.isoformat()
            if self._last_load_time
            else None,
            "cache_file": str(self.cache_file),
            "cache_valid": self.is_cache_valid(),
            "loading": self._loading,
            "frequency_tracker_stats": self._app_tracker.get_stats(),
            "frecency_tracker_stats": self._frecency_tracker.get_stats(),
        }


# Global instance for app-wide use
_global_loader: Optional[FastAppLoader] = None


def get_app_loader() -> FastAppLoader:
    """Get the global app loader instance."""
    global _global_loader
    if _global_loader is None:
        _global_loader = FastAppLoader()
    return _global_loader


def load_apps_fast(force_refresh: bool = False) -> List[Dict]:
    """Load apps using the fast loader."""
    loader = get_app_loader()
    return loader.load_apps(force_refresh=force_refresh)


def search_apps_fast(query: str, max_results: int = 50) -> List[Dict]:
    """Search apps using the fast loader with fuzzy matching."""
    loader = get_app_loader()
    return loader.search_apps(query, max_results)


def track_app_launch(app_name: str):
    """Track an app launch using the global loader."""
    loader = get_app_loader()
    loader.track_app_launch(app_name)
