# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

"""
App launch frequency tracking system based on Ulauncher patterns.
Tracks app usage and provides frequency-based ranking.
"""

import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import threading
import logging

logger = logging.getLogger("AppTracker")


class AppFrequencyTracker:
    """Tracks app launch frequency for intelligent ranking."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "locus"
        self.cache_file = self.cache_dir / "app_starts.json"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._frequency_cache: Dict[str, int] = {}
        self._lock = threading.RLock()  # Thread-safe access
        self._max_frequencies = {}  # Track max for normalization
        self._min_frequencies = {}  # Track min for normalization

        self._load_cache()

    def _load_cache(self):
        """Load frequency data from cache file."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._frequency_cache = data.get("app_starts", {})

                    # Calculate min/max for normalization
                    if self._frequency_cache:
                        frequencies = list(self._frequency_cache.values())
                        self._max_frequencies = {"value": max(frequencies) if frequencies else 1}
                        self._min_frequencies = {"value": min(frequencies) if frequencies else 0}

                logger.debug(f"Loaded {len(self._frequency_cache)} app frequency records")
            else:
                self._frequency_cache = {}
                self._max_frequencies = {"value": 1}
                self._min_frequencies = {"value": 0}

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load app frequency cache: {e}")
            self._frequency_cache = {}
            self._max_frequencies = {"value": 1}
            self._min_frequencies = {"value": 0}

    def _save_cache(self):
        """Save frequency data to cache file."""
        try:
            cache_data = {
                "app_starts": self._frequency_cache,
                "last_updated": datetime.now().isoformat(),
                "version": "1.0"
            }

            # Write to temporary file first, then rename to avoid corruption
            temp_file = self.cache_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, sort_keys=True)

            temp_file.rename(self.cache_file)
            logger.debug("Saved app frequency cache")

        except OSError as e:
            logger.warning(f"Failed to save app frequency cache: {e}")

    def increment_app_start(self, app_name: str):
        """Increment the launch count for an app."""
        if not app_name:
            return

        with self._lock:
            current_count = self._frequency_cache.get(app_name, 0)
            new_count = current_count + 1
            self._frequency_cache[app_name] = new_count

            # Update max frequency
            if new_count > self._max_frequencies.get("value", 0):
                self._max_frequencies["value"] = new_count

            # Save to disk asynchronously for better performance
            threading.Thread(target=self._save_cache, daemon=True).start()

    def get_frequency(self, app_name: str) -> int:
        """Get the launch frequency for an app."""
        with self._lock:
            return self._frequency_cache.get(app_name, 0)

    def get_frequency_weight(self, app_name: str) -> float:
        """
        Get normalized frequency weight for an app (0.0 to 1.0).
        Uses Ulauncher's 10% differential approach.
        """
        with self._lock:
            count = self._frequency_cache.get(app_name, 0)
            max_count = self._max_frequencies.get("value", 1)
            min_count = self._min_frequencies.get("value", 0)

            if max_count == min_count:
                return 0.5  # All apps equal if no variation

            # Normalize to 0.0-1.0 range
            normalized = (count - min_count) / (max_count - min_count)

            # Apply 10% differential: most frequent gets 10% boost
            # This matches Ulauncher's approach where frequent apps get up to 10% score boost
            weight = 1.0 + (normalized * 0.1)  # Range: 1.0 to 1.1

            return weight

    def get_all_frequencies(self) -> Dict[str, int]:
        """Get all app frequencies."""
        with self._lock:
            return self._frequency_cache.copy()

    def get_top_apps(self, limit: int = 10) -> list:
        """Get the most frequently launched apps."""
        with self._lock:
            sorted_apps = sorted(
                self._frequency_cache.items(),
                key=lambda x: x[1],
                reverse=True
            )
            return sorted_apps[:limit]

    def clear_cache(self):
        """Clear all frequency data."""
        with self._lock:
            self._frequency_cache.clear()
            self._max_frequencies["value"] = 1
            self._min_frequencies["value"] = 0

            # Remove cache file
            try:
                if self.cache_file.exists():
                    self.cache_file.unlink()
            except OSError as e:
                logger.warning(f"Failed to remove frequency cache file: {e}")

    def get_stats(self) -> dict:
        """Get statistics about the frequency tracker."""
        with self._lock:
            total_apps = len(self._frequency_cache)
            total_launches = sum(self._frequency_cache.values())
            avg_launches = total_launches / total_apps if total_apps > 0 else 0

            return {
                "total_apps": total_apps,
                "total_launches": total_launches,
                "average_launches_per_app": avg_launches,
                "most_frequent_app": max(self._frequency_cache.items(), key=lambda x: x[1])[0] if self._frequency_cache else None,
                "max_frequency": self._max_frequencies.get("value", 0),
                "cache_file": str(self.cache_file)
            }


# Global instance for app-wide use
_global_tracker: Optional[AppFrequencyTracker] = None


def get_app_tracker() -> AppFrequencyTracker:
    """Get the global app frequency tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = AppFrequencyTracker()
    return _global_tracker


def track_app_launch(app_name: str):
    """Track an app launch using the global tracker."""
    tracker = get_app_tracker()
    tracker.increment_app_start(app_name)


def get_app_frequency_weight(app_name: str) -> float:
    """Get frequency weight for an app using the global tracker."""
    tracker = get_app_tracker()
    return tracker.get_frequency_weight(app_name)


def get_frequency_weights_for_apps(app_names: list) -> dict:
    """Get frequency weights for multiple apps efficiently."""
    tracker = get_app_tracker()
    return {name: tracker.get_frequency_weight(name) for name in app_names}