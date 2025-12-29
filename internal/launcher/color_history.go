package launcher

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// ColorHistory manages color history with frecency tracking
type ColorHistory struct {
	colors     map[string]*ColorEntry
	maxHistory int
	mu         sync.RWMutex
	filePath   string
}

// ColorEntry represents a single color in history
type ColorEntry struct {
	Value     string    `json:"value"`
	AddedAt   time.Time `json:"added_at"`
	LastUsed  time.Time `json:"last_used"`
	Frequency int       `json:"frequency"`
}

// NewColorHistory creates a new color history manager
func NewColorHistory(dataDir string, maxHistory int) (*ColorHistory, error) {
	if maxHistory <= 0 {
		maxHistory = 50
	}

	historyFile := filepath.Join(dataDir, "color_history.json")
	history := &ColorHistory{
		colors:     make(map[string]*ColorEntry),
		maxHistory: maxHistory,
		filePath:   historyFile,
	}

	if err := history.Load(); err != nil {
		// If file doesn't exist, that's okay
		if !os.IsNotExist(err) {
			return nil, fmt.Errorf("failed to load color history: %w", err)
		}
	}

	return history, nil
}

// Add adds a color to history
func (h *ColorHistory) Add(color string) {
	h.mu.Lock()
	defer h.mu.Unlock()

	// Normalize color to lowercase
	normalized := normalizeColor(color)

	if entry, exists := h.colors[normalized]; exists {
		// Update existing entry
		entry.LastUsed = time.Now()
		entry.Frequency++
	} else {
		// Add new entry
		h.colors[normalized] = &ColorEntry{
			Value:     normalized,
			AddedAt:   time.Now(),
			LastUsed:  time.Now(),
			Frequency: 1,
		}
	}

	// Trim to max history if needed
	if len(h.colors) > h.maxHistory {
		h.trim()
	}

	// Save to file
	h.save()
}

// GetColors returns all colors sorted by frecency
func (h *ColorHistory) GetColors() []string {
	h.mu.RLock()
	defer h.mu.RUnlock()

	entries := make([]*ColorEntry, 0, len(h.colors))
	for _, entry := range h.colors {
		entries = append(entries, entry)
	}

	// Sort by frecency (frequency + recency)
	sortByFrecency(entries)

	colors := make([]string, len(entries))
	for i, entry := range entries {
		colors[i] = entry.Value
	}

	return colors
}

// SearchColors searches for colors matching the query
func (h *ColorHistory) SearchColors(query string) []string {
	h.mu.RLock()
	defer h.mu.RUnlock()

	query = normalizeColor(query)

	var matches []*ColorEntry
	for _, entry := range h.colors {
		if containsColor(entry.Value, query) {
			matches = append(matches, entry)
		}
	}

	if len(matches) == 0 {
		return []string{}
	}

	// Sort by frecency
	sortByFrecency(matches)

	colors := make([]string, len(matches))
	for i, entry := range matches {
		colors[i] = entry.Value
	}

	return colors
}

// Load loads color history from file
func (h *ColorHistory) Load() error {
	h.mu.Lock()
	defer h.mu.Unlock()

	data, err := os.ReadFile(h.filePath)
	if err != nil {
		return err
	}

	var entries []*ColorEntry
	if err := json.Unmarshal(data, &entries); err != nil {
		return err
	}

	h.colors = make(map[string]*ColorEntry)
	for _, entry := range entries {
		normalized := normalizeColor(entry.Value)
		h.colors[normalized] = entry
	}

	return nil
}

// save saves color history to file
func (h *ColorHistory) save() {
	data, err := json.Marshal(h.colors)
	if err != nil {
		return
	}

	// Create directory if it doesn't exist
	dir := filepath.Dir(h.filePath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return
	}

	os.WriteFile(h.filePath, data, 0644)
}

// trim removes oldest/least frequently used colors
func (h *ColorHistory) trim() {
	entries := make([]*ColorEntry, 0, len(h.colors))
	for _, entry := range h.colors {
		entries = append(entries, entry)
	}

	// Sort by frecency (oldest/least frequent first)
	sortByFrecency(entries)

	// Remove oldest entries
	toRemove := len(entries) - h.maxHistory
	for i := 0; i < toRemove; i++ {
		delete(h.colors, entries[i].Value)
	}
}

// normalizeColor normalizes color string to lowercase without # prefix
func normalizeColor(color string) string {
	color = colorStr(color)
	if len(color) > 0 && color[0] == '#' {
		color = color[1:]
	}
	return colorStr(color)
}

// containsColor checks if color string contains query
func containsColor(color, query string) bool {
	color = colorStr(color)
	query = colorStr(query)

	if len(query) == 0 {
		return true
	}

	return containsStr(color, query)
}

// colorStr normalizes string for comparison
func colorStr(s string) string {
	if s == "" {
		return ""
	}
	// Convert to lowercase for case-insensitive comparison
	result := make([]rune, 0, len(s))
	for _, r := range s {
		if r >= 'A' && r <= 'Z' {
			result = append(result, r+('a'-'A'))
		} else {
			result = append(result, r)
		}
	}
	return string(result)
}

// containsStr checks if s contains substr
func containsStr(s, substr string) bool {
	if len(substr) == 0 {
		return true
	}
	if len(s) < len(substr) {
		return false
	}

	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

// sortByFrecency sorts entries by frequency and recency
func sortByFrecency(entries []*ColorEntry) {
	// Simple sort: higher frequency and more recent = higher priority
	for i := 0; i < len(entries)-1; i++ {
		for j := i + 1; j < len(entries); j++ {
			if compareFrecency(entries[j], entries[i]) > 0 {
				entries[i], entries[j] = entries[j], entries[i]
			}
		}
	}
}

// compareFrecency compares two entries, returns 1 if a > b
func compareFrecency(a, b *ColorEntry) int {
	// Compare by frequency first
	if a.Frequency != b.Frequency {
		if a.Frequency > b.Frequency {
			return 1
		}
		return -1
	}

	// Then by last used time
	if a.LastUsed.After(b.LastUsed) {
		return 1
	}
	if a.LastUsed.Before(b.LastUsed) {
		return -1
	}

	return 0
}
