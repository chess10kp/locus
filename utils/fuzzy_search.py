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
"""

import re
import unicodedata
from functools import lru_cache
from typing import List, Tuple, Optional

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

    Args:
        query: Search query
        apps: List of app dictionaries
        frequency_weights: Dict mapping app names to frequency weights
        max_results: Maximum number of results

    Returns:
        List of filtered and sorted app dictionaries
    """
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
        return sorted_apps[:max_results]

    results = []
    query_norm = normalize(query)

    for app in apps:
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
    return results[:max_results]


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