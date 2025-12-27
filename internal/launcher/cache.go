package launcher

import (
	"crypto/md5"
	"fmt"
	"log"
	"sync"
	"sync/atomic"
	"time"

	"github.com/hashicorp/golang-lru/v2"
	"github.com/chess10kp/locus/internal/apps"
)

// SearchCacheEntry represents a cached search result
type SearchCacheEntry struct {
	Results    []*LauncherItem
	Timestamp  time.Time
	Query      string
	AppsHash   string
	DurationMs float64
}

// SearchCache provides LRU caching for search results
type SearchCache struct {
	cache   *lru.Cache[string, *SearchCacheEntry]
	maxSize int
	hits    int64
	misses  int64
	mu      sync.RWMutex
}

// CacheStats holds cache statistics
type CacheStats struct {
	Size    int     `json:"size"`
	MaxSize int     `json:"max_size"`
	Hits    int64   `json:"hits"`
	Misses  int64   `json:"misses"`
	HitRate float64 `json:"hit_rate"`
}

// NewSearchCache creates a new search cache with the specified maximum size
func NewSearchCache(maxSize int) (*SearchCache, error) {
	if maxSize <= 0 {
		maxSize = 100 // Default size
	}

	cache, err := lru.New[string, *SearchCacheEntry](maxSize)
	if err != nil {
		return nil, fmt.Errorf("failed to create LRU cache: %w", err)
	}

	return &SearchCache{
		cache:   cache,
		maxSize: maxSize,
		hits:    0,
		misses:  0,
	}, nil
}

// Get retrieves cached results for a query and apps hash
func (c *SearchCache) Get(query, appsHash string) ([]*LauncherItem, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	key := c.makeKey(query, appsHash)
	entry, found := c.cache.Get(key)

	if found {
		// Check if entry is still valid (apps hash matches and TTL not expired)
		if entry.AppsHash == appsHash {
			// Adaptive TTL based on search duration
			var TTL time.Duration
			if entry.DurationMs < 50 {
				TTL = 30 * time.Minute // Fast searches cached longer
			} else if entry.DurationMs < 100 {
				TTL = 10 * time.Minute // Medium searches
			} else {
				TTL = 5 * time.Minute // Slow searches cached shorter
			}

			if time.Since(entry.Timestamp) < TTL {
				atomic.AddInt64(&c.hits, 1)
				log.Printf("[SEARCH-CACHE] HIT: key='%s', returning %d cached results (TTL: %v)", key, len(entry.Results), TTL)
				return entry.Results, true
			}

			// Entry expired by TTL - remove it
			c.cache.Remove(key)
			log.Printf("[SEARCH-CACHE] EXPIRED BY TTL: removed expired entry for key='%s'", key)
		} else {
			// Entry exists but apps hash doesn't match - remove it
			c.cache.Remove(key)
			log.Printf("[SEARCH-CACHE] EXPIRED BY HASH: removed stale entry for key='%s'", key)
		}
	}

	atomic.AddInt64(&c.misses, 1)
	log.Printf("[SEARCH-CACHE] MISS: key='%s'", key)
	return nil, false
}

// Put stores search results in the cache
func (c *SearchCache) Put(query, appsHash string, results []*LauncherItem, durationMs float64) {
	c.mu.Lock()
	defer c.mu.Unlock()

	// Cache all searches now - TTL will handle expiration
	key := c.makeKey(query, appsHash)
	entry := &SearchCacheEntry{
		Results:    results,
		Timestamp:  time.Now(),
		Query:      query,
		AppsHash:   appsHash,
		DurationMs: durationMs,
	}

	// Check if we're approaching cache capacity and should evict low-value entries
	if c.cache.Len() >= c.maxSize {
		c.evictLowValueEntries()
	}

	c.cache.Add(key, entry)

	// Log with adaptive cache message
	if durationMs < 50 {
		log.Printf("[SEARCH-CACHE] STORED FAST: key='%s', %d results, duration=%.2fms", key, len(results), durationMs)
	} else if durationMs < 100 {
		log.Printf("[SEARCH-CACHE] STORED MEDIUM: key='%s', %d results, duration=%.2fms", key, len(results), durationMs)
	} else {
		log.Printf("[SEARCH-CACHE] STORED SLOW: key='%s', %d results, duration=%.2fms", key, len(results), durationMs)
	}
}

// Invalidate removes all cached entries
func (c *SearchCache) Invalidate() {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.cache.Purge()
	c.hits = 0
	c.misses = 0
}

// GetStats returns current cache statistics
func (c *SearchCache) GetStats() *CacheStats {
	c.mu.RLock()
	defer c.mu.RUnlock()

	total := c.hits + c.misses
	hitRate := float64(0)
	if total > 0 {
		hitRate = float64(c.hits) / float64(total)
	}

	return &CacheStats{
		Size:    c.cache.Len(),
		MaxSize: c.maxSize,
		Hits:    c.hits,
		Misses:  c.misses,
		HitRate: hitRate,
	}
}

// evictLowValueEntries removes least valuable entries when cache is full
func (c *SearchCache) evictLowValueEntries() {
	keys := c.cache.Keys()
	evictCount := len(keys) / 4 // Evict 25% of cache

	log.Printf("[SEARCH-CACHE] Evicting %d low-value entries from cache of size %d", evictCount, len(keys))

	evicted := 0
	for _, key := range keys {
		if evicted >= evictCount {
			break
		}

		if entry, found := c.cache.Get(key); found {
			// Prioritize evicting slow searches and old entries
			age := time.Since(entry.Timestamp)
			value := entry.DurationMs // Slow searches have less value

			// If entry is very old (> 30 minutes) or very slow (> 200ms), evict it
			if age > 30*time.Minute || value > 200 {
				c.cache.Remove(key)
				evicted++
			}
		}
	}

	log.Printf("[SEARCH-CACHE] Evicted %d low-value entries", evicted)
}

// makeKey creates a cache key from query and apps hash
func (c *SearchCache) makeKey(query, appsHash string) string {
	// Use lowercase query for case-insensitive matching
	return fmt.Sprintf("%s:%s", query, appsHash)
}

// ComputeAppsHash generates a hash for the apps list for cache invalidation
func ComputeAppsHash(apps []apps.App) string {
	if len(apps) == 0 {
		return ""
	}

	// Simple hash based on length and first/last app names
	// This matches the Python implementation approach
	data := fmt.Sprintf("%d:%s:%s",
		len(apps),
		apps[0].Name,
		apps[len(apps)-1].Name,
	)

	hash := md5.Sum([]byte(data))
	return fmt.Sprintf("%x", hash)
}
