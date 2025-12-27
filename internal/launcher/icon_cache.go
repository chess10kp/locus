package launcher

import (
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/gotk3/gotk3/gdk"
	"github.com/gotk3/gotk3/gtk"
	"github.com/hashicorp/golang-lru/v2"
	"github.com/chess10kp/locus/internal/config"
)

// IconCache provides efficient icon caching for GTK3
type IconCache struct {
	cache     *lru.Cache[string, *gdk.Pixbuf]
	theme     *gtk.IconTheme
	maxSize   int
	mu        sync.RWMutex
	fallback  string
	cacheHits int64
	cacheMiss int64
}

// NewIconCache creates a new icon cache with specified size
func NewIconCache(cfg *config.Config) (*IconCache, error) {
	if cfg == nil {
		return nil, fmt.Errorf("config is nil")
	}

	// Use configured cache size, default to 200
	maxSize := cfg.Launcher.Icons.CacheSize
	if maxSize <= 0 {
		maxSize = 200
	}

	cache, err := lru.New[string, *gdk.Pixbuf](maxSize)
	if err != nil {
		return nil, fmt.Errorf("failed to create icon cache: %w", err)
	}

	// Get the default icon theme
	iconTheme, err := gtk.IconThemeGetDefault()
	if err != nil {
		return nil, fmt.Errorf("failed to get default icon theme: %w", err)
	}

	fallback := cfg.Launcher.Icons.FallbackIcon
	if fallback == "" {
		fallback = "image-missing"
	}

	return &IconCache{
		cache:    cache,
		theme:    iconTheme,
		maxSize:  maxSize,
		fallback: fallback,
	}, nil
}

// GetIcon retrieves an icon from cache or loads it if not cached
func (ic *IconCache) GetIcon(name string, size int) (*gdk.Pixbuf, error) {
	if name == "" {
		name = ic.fallback
	}

	key := fmt.Sprintf("%s@%d", name, size)

	// Try cache first
	ic.mu.RLock()
	pixbuf, hit := ic.cache.Get(key)
	ic.mu.RUnlock()

	if hit && pixbuf != nil {
		log.Printf("[ICON-CACHE] HIT: %s", key)
		return pixbuf, nil
	}

	// Cache miss - load icon
	ic.mu.Lock()
	defer ic.mu.Unlock()

	// Double-check after acquiring write lock
	if pixbuf, ok := ic.cache.Get(key); ok && pixbuf != nil {
		log.Printf("[ICON-CACHE] DOUBLE-CHECK HIT: %s", key)
		return pixbuf, nil
	}

	log.Printf("[ICON-CACHE] MISS: %s", key)

	// Load from theme - check if icon exists first
	hasIcon := ic.theme.HasIcon(name)
	if !hasIcon {
		log.Printf("[ICON-CACHE] Icon '%s' not found in theme, returning nil", name)
		return nil, fmt.Errorf("icon '%s' not found in theme", name)
	}

	pixbuf, err := ic.theme.LoadIcon(name, size, gtk.ICON_LOOKUP_USE_BUILTIN)
	if err != nil || pixbuf == nil {
		// Try fallback icon if not already trying fallback
		if name != ic.fallback {
			log.Printf("[ICON-CACHE] Failed to load '%s' (%v), trying fallback '%s'", name, err, ic.fallback)
			ic.mu.Unlock()
			defer ic.mu.Lock()
			return ic.GetIcon(ic.fallback, size)
		}
		log.Printf("[ICON-CACHE] Failed to load fallback icon '%s': %v", ic.fallback, err)
		return nil, err
	}

	// Cache the loaded icon
	ic.cache.Add(key, pixbuf)
	log.Printf("[ICON-CACHE] STORED: %s (cache size: %d)", key, ic.cache.Len())

	return pixbuf, nil
}

// PreloadCommonIcons loads commonly used icons into cache
func (ic *IconCache) PreloadCommonIcons(commonIcons []string, size int) {
	log.Printf("[ICON-CACHE] Preloading %d common icons", len(commonIcons))

	preloadStart := time.Now()
	var wg sync.WaitGroup
	semaphore := make(chan struct{}, 5) // Limit concurrent loading

	for _, iconName := range commonIcons {
		wg.Add(1)
		go func(name string) {
			defer wg.Done()
			semaphore <- struct{}{}        // Acquire
			defer func() { <-semaphore }() // Release

			ic.GetIcon(name, size)
		}(iconName)
	}

	wg.Wait()
	log.Printf("[ICON-CACHE] Preloaded %d icons in %v", len(commonIcons), time.Since(preloadStart))
}

// GetStats returns cache statistics
func (ic *IconCache) GetStats() (hits, misses int, hitRate float64, size int) {
	ic.mu.RLock()
	defer ic.mu.RUnlock()

	hits = int(ic.cacheHits)
	misses = int(ic.cacheMiss)
	size = ic.cache.Len()

	total := hits + misses
	if total > 0 {
		hitRate = float64(hits) / float64(total) * 100
	}

	return hits, misses, hitRate, size
}

// Clear empties the cache
func (ic *IconCache) Clear() {
	ic.mu.Lock()
	defer ic.mu.Unlock()

	ic.cache.Purge()
	log.Printf("[ICON-CACHE] Cache cleared")
}

// SetFallback updates the fallback icon name
func (ic *IconCache) SetFallback(fallback string) {
	ic.mu.Lock()
	defer ic.mu.Unlock()
	ic.fallback = fallback
	log.Printf("[ICON-CACHE] Fallback icon set to: %s", fallback)
}
