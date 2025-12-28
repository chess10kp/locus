package launcher

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/hashicorp/golang-lru/v2"
)

// ThumbnailCacheEntry represents a cached thumbnail
type ThumbnailCacheEntry struct {
	Data      []byte
	Timestamp time.Time
	Size      int64
}

// ThumbnailCache provides LRU caching for image thumbnails
type ThumbnailCache struct {
	cache       *lru.Cache[string, *ThumbnailCacheEntry]
	maxItems    int
	currentSize int64
	maxSizeMB   int64
	mu          sync.RWMutex
	cacheDir    string
}

// NewThumbnailCache creates a new thumbnail cache
func NewThumbnailCache(maxItems int, maxSizeMB int64) (*ThumbnailCache, error) {
	if maxItems <= 0 {
		maxItems = 100
	}
	if maxSizeMB <= 0 {
		maxSizeMB = 100
	}

	cache, err := lru.New[string, *ThumbnailCacheEntry](maxItems)
	if err != nil {
		return nil, fmt.Errorf("failed to create LRU cache: %w", err)
	}

	homeDir, err := os.UserCacheDir()
	if err != nil {
		return nil, fmt.Errorf("failed to get cache directory: %w", err)
	}

	cacheDir := filepath.Join(homeDir, "locus", "thumbnails")
	if err := os.MkdirAll(cacheDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create cache directory: %w", err)
	}

	return &ThumbnailCache{
		cache:       cache,
		maxItems:    maxItems,
		currentSize: 0,
		maxSizeMB:   maxSizeMB,
		cacheDir:    cacheDir,
	}, nil
}

// Get retrieves a cached thumbnail
func (c *ThumbnailCache) Get(key string) ([]byte, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	entry, found := c.cache.Get(key)
	if found {
		log.Printf("[THUMBNAIL-CACHE] HIT: key='%s', size=%d bytes", key, entry.Size)
		return entry.Data, true
	}

	log.Printf("[THUMBNAIL-CACHE] MISS: key='%s'", key)
	return nil, false
}

// Put stores a thumbnail in the cache
func (c *ThumbnailCache) Put(key string, data []byte) {
	c.mu.Lock()
	defer c.mu.Unlock()

	entry := &ThumbnailCacheEntry{
		Data:      data,
		Timestamp: time.Now(),
		Size:      int64(len(data)),
	}

	// Check if we need to make space
	maxCacheSize := c.maxSizeMB * 1024 * 1024 // Convert to bytes
	for c.currentSize+entry.Size > maxCacheSize && c.cache.Len() > 0 {
		if c.evictOldest() {
			continue
		}
		break
	}

	c.cache.Add(key, entry)
	c.currentSize += entry.Size

	log.Printf("[THUMBNAIL-CACHE] STORED: key='%s', size=%d bytes, total=%d/%d bytes",
		key, entry.Size, c.currentSize, maxCacheSize)
}

// GetFromCacheDir tries to load a thumbnail from disk cache
func (c *ThumbnailCache) GetFromCacheDir(key string) ([]byte, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	cachePath := filepath.Join(c.cacheDir, key)
	data, err := os.ReadFile(cachePath)
	if err != nil {
		return nil, false
	}

	log.Printf("[THUMBNAIL-CACHE] DISK HIT: key='%s', size=%d bytes", key, len(data))
	return data, true
}

// SaveToCacheDir saves a thumbnail to disk cache
func (c *ThumbnailCache) SaveToCacheDir(key string, data []byte) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	cachePath := filepath.Join(c.cacheDir, key)
	if err := os.WriteFile(cachePath, data, 0644); err != nil {
		return fmt.Errorf("failed to save thumbnail to disk: %w", err)
	}

	log.Printf("[THUMBNAIL-CACHE] DISK STORED: key='%s', size=%d bytes", key, len(data))
	return nil
}

// Clear removes all cached thumbnails
func (c *ThumbnailCache) Clear() {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.cache.Purge()
	c.currentSize = 0
	log.Printf("[THUMBNAIL-CACHE] Cleared all cache entries")
}

// evictOldest removes the oldest entry from cache
func (c *ThumbnailCache) evictOldest() bool {
	keys := c.cache.Keys()
	if len(keys) == 0 {
		return false
	}

	oldestKey := keys[len(keys)-1]
	if entry, found := c.cache.Get(oldestKey); found {
		c.cache.Remove(oldestKey)
		c.currentSize -= entry.Size
		log.Printf("[THUMBNAIL-CACHE] EVICTED: key='%s', size=%d bytes", oldestKey, entry.Size)
		return true
	}

	return false
}

// GetCacheStats returns cache statistics
func (c *ThumbnailCache) GetCacheStats() map[string]interface{} {
	c.mu.RLock()
	defer c.mu.RUnlock()

	return map[string]interface{}{
		"size":         c.cache.Len(),
		"max_items":    c.maxItems,
		"current_size": c.currentSize,
		"max_size_mb":  c.maxSizeMB,
		"cache_dir":    c.cacheDir,
	}
}
