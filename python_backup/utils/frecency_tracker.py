# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import json
import threading
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger("FrecencyTracker")


class FrecencyTracker:
    """Simple frecency tracker: frequency × recency decay."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "locus"
        self.cache_file = self.cache_dir / "frecency_history.json"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._data: Dict = {"items": {}, "last_updated": None}
        self._lock = threading.RLock()
        self._cache_dirty = False
        self._cached_weights: Dict[str, float] = {}
        self._max_frecency = 0.0

        self._load_cache()

    def _load_cache(self):
        """Load frecency data from cache file."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._data = data if isinstance(data, dict) else {"items": {}}
                logger.debug(
                    f"Loaded frecency history: {len(self._data.get('items', {}))} items"
                )
        except Exception as e:
            logger.warning(f"Failed to load frecency cache: {e}")
            self._data = {"items": {}}

    def _save_cache_async(self):
        """Save frecency data to cache file asynchronously."""
        if not self._cache_dirty:
            return

        def save_thread():
            try:
                self._data["last_updated"] = datetime.now().isoformat()
                temp_file = self.cache_file.with_suffix(".tmp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2)
                temp_file.rename(self.cache_file)
                with self._lock:
                    self._cache_dirty = False
                logger.debug("Saved frecency cache")
            except Exception as e:
                logger.warning(f"Failed to save frecency cache: {e}")

        threading.Thread(target=save_thread, daemon=True).start()

    def increment(self, item_name: str):
        """Increment the usage count for an item."""
        if not item_name:
            return

        now_ts = datetime.now().isoformat()
        with self._lock:
            if item_name not in self._data["items"]:
                self._data["items"][item_name] = {
                    "count": 0,
                    "last_used": None,
                    "timestamps": [],
                }

            item = self._data["items"][item_name]
            item["count"] += 1
            item["last_used"] = now_ts
            item["timestamps"].append(now_ts)
            if len(item["timestamps"]) > 10:  # Keep only last 10 timestamps for pruning
                item["timestamps"] = item["timestamps"][-10:]

            self._cache_dirty = True
            self._cached_weights.clear()  # Invalidate cache
            self._max_frecency = 0.0

        # Save asynchronously
        threading.Thread(target=self._save_cache_async, daemon=True).start()

    def get_frecency_score(self, item_name: str, recency_multipliers=None) -> float:
        """Get the frecency score for an item."""
        if recency_multipliers is None:
            recency_multipliers = {"hour": 4.0, "day": 2.0, "week": 1.0, "older": 0.5}

        if item_name not in self._data["items"]:
            return 0.0

        item = self._data["items"][item_name]
        if not item["last_used"]:
            return float(item["count"])

        try:
            last_used = datetime.fromisoformat(item["last_used"])
        except:
            return float(item["count"])

        hours_since = (datetime.now() - last_used).total_seconds() / 3600

        if hours_since < 1:
            multiplier = recency_multipliers["hour"]
        elif hours_since < 24:
            multiplier = recency_multipliers["day"]
        elif hours_since < 168:  # 7 days
            multiplier = recency_multipliers["week"]
        else:
            multiplier = recency_multipliers["older"]

        return float(item["count"]) * multiplier

    def get_normalized_weight(self, item_name: str, recency_multipliers=None) -> float:
        """Get normalized frecency weight (0.0 to 1.0)."""
        with self._lock:
            if not self._cached_weights:
                self._rebuild_cache(recency_multipliers)

            return self._cached_weights.get(item_name, 0.0)

    def _rebuild_cache(self, recency_multipliers=None):
        """Rebuild the cached normalized weights."""
        if not self._data["items"]:
            self._cached_weights = {}
            self._max_frecency = 0.0
            return

        scores = {}
        for name in self._data["items"]:
            scores[name] = self.get_frecency_score(name, recency_multipliers)

        self._max_frecency = max(scores.values()) if scores else 1.0

        if self._max_frecency > 0:
            self._cached_weights = {
                name: score / self._max_frecency for name, score in scores.items()
            }
        else:
            self._cached_weights = {}

    def prune_old_entries(self, max_age_days=90):
        """Prune old entries that haven't been used recently."""
        cutoff = datetime.now() - timedelta(days=max_age_days)
        with self._lock:
            to_remove = []
            for name, item in self._data["items"].items():
                if item["count"] == 0:
                    to_remove.append(name)
                    continue
                if item["last_used"]:
                    try:
                        last_used = datetime.fromisoformat(item["last_used"])
                        if last_used < cutoff:
                            to_remove.append(name)
                    except:
                        pass

            for name in to_remove:
                del self._data["items"][name]

            if to_remove:
                self._cache_dirty = True
                self._cached_weights.clear()
                self._save_cache_async()
                logger.debug(f"Pruned {len(to_remove)} old frecency entries")

    def get_stats(self) -> Dict:
        """Get statistics about the frecency tracker."""
        with self._lock:
            total_items = len(self._data["items"])
            total_uses = sum(item["count"] for item in self._data["items"].values())
            max_count = max(
                (item["count"] for item in self._data["items"].values()), default=0
            )
            return {
                "total_items": total_items,
                "total_uses": total_uses,
                "max_count": max_count,
                "cache_file": str(self.cache_file),
                "cached_weights_count": len(self._cached_weights),
            }


_global_tracker: Optional[FrecencyTracker] = None


def get_frecency_tracker() -> FrecencyTracker:
    """Get the global frecency tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = FrecencyTracker()
    return _global_tracker


# Unit tests
try:
    import pytest

    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

if HAS_PYTEST:
    import tempfile
    import time
    from pathlib import Path

    class TestFrecencyTracker:
        def setup_method(self):
            """Create a temporary cache directory for each test."""
            self.temp_dir = Path(tempfile.mkdtemp())
            self.tracker = FrecencyTracker(cache_dir=self.temp_dir)

        def teardown_method(self):
            """Clean up temporary files."""
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)

        def test_increment_new_item(self):
            """Test incrementing a new item."""
            self.tracker.increment("test_app")
            assert (
                self.tracker.get_frecency_score("test_app") == 4.0
            )  # Recent multiplier
            assert "test_app" in self.tracker._data["items"]

        def test_increment_existing_item(self):
            """Test incrementing an existing item."""
            self.tracker.increment("test_app")
            initial_score = self.tracker.get_frecency_score("test_app")

            # Wait a tiny bit to ensure different timestamp
            time.sleep(0.01)
            self.tracker.increment("test_app")

            new_score = self.tracker.get_frecency_score("test_app")
            assert new_score > initial_score

        def test_get_frecency_score_no_usage(self):
            """Test frecency score for unused item."""
            score = self.tracker.get_frecency_score("unused_app")
            assert score == 0.0

        def test_get_frecency_score_with_count_no_timestamp(self):
            """Test frecency score for item with count but no timestamp."""
            with self.tracker._lock:
                self.tracker._data["items"]["old_app"] = {
                    "count": 5,
                    "last_used": None,
                    "timestamps": [],
                }
            score = self.tracker.get_frecency_score("old_app")
            assert score == 5.0

        def test_custom_recency_multipliers(self):
            """Test custom recency multipliers."""
            custom_multipliers = {"hour": 10.0, "day": 5.0, "week": 2.0, "older": 0.1}
            self.tracker.increment("test_app")
            score = self.tracker.get_frecency_score("test_app", custom_multipliers)
            assert score == 10.0  # Using hour multiplier

        def test_normalized_weight_caching(self):
            """Test that normalized weights are cached."""
            self.tracker.increment("app1")
            self.tracker.increment("app2")

            # First call should build cache
            weight1 = self.tracker.get_normalized_weight("app1")
            assert len(self.tracker._cached_weights) == 2

            # Second call should use cache
            weight1_cached = self.tracker.get_normalized_weight("app1")
            assert weight1 == weight1_cached

            # Increment should clear cache
            self.tracker.increment("app1")
            assert len(self.tracker._cached_weights) == 0

        def test_prune_old_entries(self):
            """Test pruning old entries."""
            # Add current item
            self.tracker.increment("recent_app")

            # Manually add old item
            old_time = (datetime.now() - timedelta(days=100)).isoformat()
            with self.tracker._lock:
                self.tracker._data["items"]["old_app"] = {
                    "count": 1,
                    "last_used": old_time,
                    "timestamps": [old_time],
                }

            assert "old_app" in self.tracker._data["items"]
            self.tracker.prune_old_entries(max_age_days=90)
            assert "old_app" not in self.tracker._data["items"]
            assert "recent_app" in self.tracker._data["items"]

        def test_thread_safety(self):
            """Test thread safety of increment operations."""
            import threading

            def increment_worker(app_name, count):
                for _ in range(count):
                    self.tracker.increment(app_name)
                    time.sleep(0.001)  # Small delay to encourage race conditions

            threads = []
            for i in range(5):
                t = threading.Thread(target=increment_worker, args=(f"app{i}", 10))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            total_count = sum(
                item["count"] for item in self.tracker._data["items"].values()
            )
            assert total_count == 50  # 5 threads * 10 increments each

        def test_persistence(self):
            """Test saving and loading from cache."""
            self.tracker.increment("persistent_app")
            score_before = self.tracker.get_frecency_score("persistent_app")

            # Force save and create new instance
            self.tracker._save_cache_async()
            time.sleep(0.1)  # Wait for async save

            new_tracker = FrecencyTracker(cache_dir=self.temp_dir)
            score_after = new_tracker.get_frecency_score("persistent_app")

            # Scores might differ slightly due to time passage, but should be close
            assert abs(score_before - score_after) < 0.1
