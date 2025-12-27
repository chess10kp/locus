# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

"""
High-performance fuzzy search implementation using RapidFuzz.
Uses RapidFuzz's process module for batch scoring - significantly faster than manual loops.
Optimized for 10k+ items with two-stage filtering and result caching.
"""

import time
import logging
from collections import OrderedDict
from functools import lru_cache
from typing import List, Tuple, Optional, Dict, Any
from rapidfuzz import process, fuzz, utils

logger = logging.getLogger("FuzzySearch")


def normalize(text: str) -> str:
    """
    Normalize text for better matching.
    Removes accents and converts to lowercase.
    """
    if not text:
        return ""

    # Use RapidFuzz's default processor which handles normalization
    return utils.default_process(text)


class SearchCache:
    """LRU cache for search results to avoid recomputing identical queries."""

    def __init__(self, max_size: int = 100):
        self.cache: OrderedDict[str, tuple] = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, query: str, apps_hash: int) -> Optional[List[Dict[str, Any]]]:
        """Get cached results for a query."""
        key = f"{query.lower()}:{apps_hash}"
        if key in self.cache:
            self.hits += 1
            self.cache.move_to_end(key)
            return self.cache[key][1]
        self.misses += 1
        return None

    def put(self, query: str, apps_hash: int, results: List[Dict], duration_ms: float):
        """Cache search results."""
        key = f"{query.lower()}:{apps_hash}"
        # Only cache fast searches (< 100ms) to avoid caching slow queries
        if duration_ms < 100:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = (time.time(), results)

            # Evict oldest if over capacity
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)

    def invalidate(self):
        """Clear all cached results."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            "size": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
        }


# Global search cache instance
_search_cache = SearchCache(max_size=100)


def get_search_cache() -> SearchCache:
    """Get the global search cache instance."""
    return _search_cache


def get_apps_hash(apps: List[Dict]) -> int:
    """Get a hash of the apps list for cache invalidation."""
    if not apps:
        return 0
    return hash((len(apps), apps[0].get("name", "") if apps else ""))


def search_items(
    query: str,
    items: List[Tuple[str, float]],
    min_score: float = 0.3,
    max_results: int = 50,
) -> List[Tuple[Any, float, Any]]:
    """
    Search through items with scores using RapidFuzzy fuzzy matching.

    Args:
        query: Search query
        items: List of (text, score) tuples
        min_score: Minimum score threshold (0-100 for RapidFuzz)
        max_results: Maximum number of results to return

    Returns:
        List of (text, final_score, original_text) tuples sorted by score
    """
    if not query:
        return [
            (text, score, text)
            for text, score in sorted(items, key=lambda x: x[1], reverse=True)[
                :max_results
            ]
        ]

    # Extract texts for batch processing
    texts = [text for text, _ in items]

    # Use RapidFuzz process.extract for fast batch matching
    # Returns list of (match, score, index) tuples
    results = process.extract(
        query,
        texts,
        scorer=fuzz.WRatio,
        processor=normalize,
        limit=max_results * 2,  # Get more to filter by base_score later
    )

    # Combine with base scores
    final_results = []
    for match_text, fuzzy_score, idx in results:
        # Convert fuzzy_score (0-100) to 0-1 range for consistency
        fuzzy_score_normalized = fuzzy_score / 100.0
        base_score = items[idx][1]
        final_score = fuzzy_score_normalized * base_score

        # Filter by minimum score
        if final_score >= min_score:
            final_results.append((match_text, final_score, match_text))

    # Sort by score (descending) and limit results
    final_results.sort(key=lambda x: x[1], reverse=True)
    return final_results[:max_results]


def filter_apps_with_fuzzy(
    query: str,
    apps: List[Dict[str, Any]],
    frequency_weights: Optional[Dict[str, float]] = None,
    frecency_weights: Optional[Dict[str, float]] = None,
    max_results: int = 50,
    frecency_boost_factor: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Filter apps using RapidFuzz fuzzy search with frequency and frecency weighting.
    Optimized for 10k+ items using process.extract for batch scoring.

    Args:
        query: Search query
        apps: List of app dictionaries
        frequency_weights: Dict mapping app names to frequency weights
        frecency_weights: Dict mapping app names to frecency weights (0-1 normalized)
        max_results: Maximum number of results
        frecency_boost_factor: Multiplier for frecency boost (default 0.3)

    Returns:
        List of filtered and sorted app dictionaries
    """
    start_time = time.time()

    # Check cache first
    cache = get_search_cache()
    apps_hash = get_apps_hash(apps)
    cached_results = cache.get(query, apps_hash)
    if cached_results is not None:
        return cached_results

    if not query:
        # Return top apps by frecency if no query
        if frecency_weights:
            sorted_apps = sorted(
                apps,
                key=lambda x: frecency_weights.get(x.get("name", ""), 0),
                reverse=True,
            )
        elif frequency_weights:
            # Fallback to frequency if no frecency weights
            sorted_apps = sorted(
                apps,
                key=lambda x: frequency_weights.get(x.get("name", ""), 0),
                reverse=True,
            )
        else:
            sorted_apps = apps[:max_results]
        results = sorted_apps[:max_results]
    else:
        # Batch fuzzy matching using RapidFuzz process.extract
        # This handles fuzzy matching efficiently without needing pre-filtering
        app_names = [app.get("name", "") for app in apps]
        app_dict = {app.get("name", ""): app for app in apps}

        # Use RapidFuzz for fast batch fuzzy matching
        # limit parameter allows RapidFuzz to optimize internally
        matches = process.extract(
            query,
            app_names,
            scorer=fuzz.WRatio,
            processor=normalize,
            limit=max_results * 2,
            score_cutoff=25,  # Minimum similarity score (25/100 = 25%)
        )

        # Combine fuzzy scores with frequency and frecency weights
        results = []
        for app_name, fuzzy_score, _ in matches:
            # fuzzy_score is 0-100 from RapidFuzz
            fuzzy_score_normalized = fuzzy_score / 100.0

            # Get frequency weight (default to 1.0 if no tracking)
            freq_weight = 1.0
            if frequency_weights:
                freq_weight = frequency_weights.get(app_name, 1.0)
                # Normalize frequency weight to range [0.5, 1.5]
                if freq_weight > 0:
                    freq_weight = 0.5 + min(freq_weight, 1.0)

            # Get frecency weight (default to 0.0 if no tracking)
            frecency_weight = 0.0
            if frecency_weights:
                frecency_weight = frecency_weights.get(app_name, 0.0)

            # Combine scores: fuzzy * frequency + frecency_boost
            final_score = fuzzy_score_normalized * freq_weight + (
                frecency_weight * frecency_boost_factor
            )

            # Add to results
            if app_name in app_dict:
                app_copy = app_dict[app_name].copy()
                app_copy["_search_score"] = final_score
                results.append(app_copy)

        # Sort by score (descending) and limit results
        results.sort(key=lambda x: x["_search_score"], reverse=True)
        results = results[:max_results]

    # Cache the results
    duration_ms = (time.time() - start_time) * 1000
    cache.put(query, apps_hash, results, duration_ms)

    # Log slow searches
    if duration_ms > 50:
        logger.warning(
            f"Slow search '{query}': {duration_ms:.2f}ms ({len(results)} results from {len(apps)} apps)"
        )
    else:
        logger.debug(f"Search '{query}': {duration_ms:.2f}ms ({len(results)} results)")

    return results


@lru_cache(maxsize=100)
def create_searchable_fields(
    name: str,
    exec_name: str = "",
    description: str = "",
    keywords: Optional[List[str]] = None,
    frequency_weight: float = 1.0,
) -> List[Tuple[str, float]]:
    """
    Create searchable fields with weights.

    Args:
        name: App name
        exec_name: Executable name
        description: App description
        keywords: List of keywords
        frequency_weight: Usage frequency weight

    Returns:
        List of (text, weight) tuples for searching
    """
    fields = []

    # App name has highest weight
    if name:
        fields.append((name, 1.0 * frequency_weight))

    # Executable name
    if exec_name:
        fields.append((exec_name, 0.8 * frequency_weight))

    # Description
    if description:
        fields.append((description, 0.7 * frequency_weight))

    # Keywords
    if keywords:
        for keyword in keywords:
            if keyword:
                fields.append((keyword, 0.6 * frequency_weight))

    return fields
