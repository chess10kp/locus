# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

"""
High-performance fuzzy search implementation based on Ulauncher patterns.
Uses Levenshtein distance for fast fuzzy matching with LRU caching.
Optimized for 10k+ items with two-stage filtering and result caching.
"""

import re
import unicodedata
import time
import logging
from collections import OrderedDict
from functools import lru_cache
from typing import List, Tuple, Optional, Dict

logger = logging.getLogger("FuzzySearch")

try:
    # Try to use python-Levenshtein (fastest, ~10x faster than native)
    import Levenshtein
except ImportError:
    try:
        # Fall back to rapidfuzz
        import rapidfuzz.distance as Levenshtein
    except ImportError:
        # Fall back to native Python
        Levenshtein = None


def normalize(text: str) -> str:
    """
    Normalize text for better matching.
    Removes accents and converts to lowercase.
    """
    if not text:
        return ""

    # Remove accents
    normalized = unicodedata.normalize("NFKD", text)
    # Remove diacritical marks and convert to lowercase
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()


class SearchCache:
    """LRU cache for search results to avoid recomputing identical queries."""

    def __init__(self, max_size: int = 100):
        self.cache: OrderedDict[str, tuple] = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, query: str, apps_hash: int) -> Optional[List[Dict]]:
        """Get cached results for a query."""
        key = f"{query.lower()}:{apps_hash}"
        if key in self.cache:
            self.hits += 1
            self.cache.move_to_end(key)
            return self.cache[key][1]  # Return results
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
    # Simple hash based on count and first app name
    # This is efficient and works for cache invalidation when apps change
    if not apps:
        return 0
    return hash((len(apps), apps[0].get("name", "") if apps else ""))


def adaptive_limit(query: str, max_results: int = 50) -> int:
    """
    Dynamically adjust the candidate limit based on query characteristics.
    Shorter queries need more candidates, longer queries need fewer.
    """
    query_len = len(query.strip())

    if query_len == 0:
        # Empty query: just return max_results
        return max_results
    elif query_len <= 2:
        # Very short queries: check more candidates
        return min(max_results * 10, 1000)
    elif query_len <= 4:
        # Short queries: check moderate candidates
        return min(max_results * 5, 500)
    else:
        # Longer queries: check fewer candidates (more specific)
        return min(max_results * 3, 300)


def fast_prefix_filter(query: str, apps: List[Dict], limit: int) -> List[Dict]:
    """
    Fast prefix-based filtering to reduce the number of apps for fuzzy scoring.
    This is much faster than fuzzy matching all apps.
    """
    if not query:
        return apps[:limit]

    query_norm = normalize(query).lower()
    candidates = []

    # First pass: exact prefix matches
    for app in apps:
        name = app.get("name", "")
        if name and normalize(name).lower().startswith(query_norm):
            candidates.append(app)
            if len(candidates) >= limit:
                return candidates

    # If we don't have enough candidates, add substring matches
    if len(candidates) < limit:
        for app in apps:
            if app in candidates:
                continue
            name = app.get("name", "")
            if name and query_norm in normalize(name).lower():
                candidates.append(app)
                if len(candidates) >= limit * 2:  # Get more for substring
                    return candidates[:limit]

    return candidates[:limit]


@lru_cache(maxsize=1000)
def get_score(query: str, text: str) -> float:
    """
    Calculate fuzzy search score between query and text.
    Returns a score between 0.0 (no match) and 1.0 (perfect match).

    Uses Longest Common Subsequence algorithm with optimizations from Ulauncher.
    """
    if not query or not text:
        return 0.0

    # Normalize both strings
    query_norm = normalize(query)
    text_norm = normalize(text)

    # Early exit for perfect match
    if query_norm == text_norm:
        return 1.0

    # Early exit for empty query
    if not query_norm:
        return 0.0

    # If query is longer than text, can't be a good match
    if len(query_norm) > len(text_norm) * 1.5:
        return 0.0

    # Use Levenshtein if available (much faster)
    if Levenshtein:
        try:
            # Calculate normalized similarity
            distance = Levenshtein.distance(query_norm, text_norm)
            max_len = max(len(query_norm), len(text_norm))
            similarity = 1.0 - (distance / max_len)
            return similarity
        except Exception:
            # Fall back to native implementation if Levenshtein fails
            pass

    # Native Python Longest Common Subsequence implementation
    return _lcs_similarity(query_norm, text_norm)


def _lcs_similarity(query: str, text: str) -> float:
    """
    Calculate similarity using Longest Common Subsequence.
    Fallback implementation when Levenshtein is not available.
    """
    if not query or not text:
        return 0.0

    # Dynamic programming for LCS
    m, n = len(query), len(text)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if query[i - 1] == text[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    # Normalize similarity
    lcs_length = dp[m][n]
    return lcs_length / max(len(query), len(text))


def search_items(
    query: str,
    items: List[Tuple[str, float]],
    min_score: float = 0.3,
    max_results: int = 50
) -> List[Tuple[str, float, str]]:
    """
    Search through items with scores using fuzzy matching.

    Args:
        query: Search query
        items: List of (text, score) tuples
        min_score: Minimum score threshold
        max_results: Maximum number of results to return

    Returns:
        List of (text, final_score, original_text) tuples sorted by score
    """
    if not query:
        # Return top items by score if no query
        return [(text, score, text) for text, score in sorted(items, key=lambda x: x[1], reverse=True)[:max_results]]

    results = []
    query_lower = normalize(query)

    for text, base_score in items:
        # Calculate fuzzy match score
        fuzzy_score = get_score(query_lower, text)

        # Combine base score with fuzzy score
        final_score = fuzzy_score * base_score

        # Filter by minimum score
        if final_score >= min_score:
            results.append((text, final_score, text))

    # Sort by score (descending) and limit results
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:max_results]


def filter_apps_with_fuzzy(
    query: str,
    apps: List[dict],
    frequency_weights: dict = None,
    max_results: int = 50
) -> List[dict]:
    """
    Filter apps using fuzzy search with frequency weighting.
    Optimized for 10k+ items with two-stage filtering and result caching.

    Args:
        query: Search query
        apps: List of app dictionaries
        frequency_weights: Dict mapping app names to frequency weights
        max_results: Maximum number of results

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
        # Return top apps by frequency if no query
        if frequency_weights:
            sorted_apps = sorted(
                apps,
                key=lambda x: frequency_weights.get(x.get("name", ""), 0),
                reverse=True
            )
        else:
            sorted_apps = apps[:max_results]
        results = sorted_apps[:max_results]
    else:
        # Stage 1: Fast prefix filtering to reduce candidates
        candidate_limit = adaptive_limit(query, max_results)
        candidates = fast_prefix_filter(query, apps, candidate_limit)

        # Stage 2: Fuzzy scoring on reduced candidate set
        results = []
        query_norm = normalize(query)

        for app in candidates:
            app_name = app.get("name", "")
            if not app_name:
                continue

            # Calculate fuzzy match score for app name
            name_score = get_score(query_norm, app_name)

            # Get frequency weight (default to 1.0 if no tracking)
            freq_weight = 1.0
            if frequency_weights:
                freq_weight = frequency_weights.get(app_name, 1.0)
                # Normalize frequency weight to range [0.5, 1.5] like Ulauncher
                if freq_weight > 0:
                    freq_weight = 0.5 + min(freq_weight, 1.0)

            # Combine scores
            final_score = name_score * freq_weight

            # Add to results if score is good enough
            if final_score >= 0.3:  # Minimum threshold
                app_copy = app.copy()
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
        logger.warning(f"Slow search '{query}': {duration_ms:.2f}ms ({len(results)} results from {len(apps)} apps)")
    else:
        logger.debug(f"Search '{query}': {duration_ms:.2f}ms ({len(results)} results)")

    return results


@lru_cache(maxsize=100)
def create_searchable_fields(
    name: str,
    exec_name: str = "",
    description: str = "",
    keywords: list = None,
    frequency_weight: float = 1.0
) -> List[Tuple[str, float]]:
    """
    Create searchable fields with weights, similar to Ulauncher's approach.

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