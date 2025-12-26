package core

import (
	"sync"

	"github.com/gotk3/gotk3/gtk"
)

// WidgetPool manages reusable GTK widgets for better performance
type WidgetPool struct {
	rows []*gtk.ListBoxRow
	mu   sync.Mutex
}

// NewWidgetPool creates a new widget pool
func NewWidgetPool() *WidgetPool {
	return &WidgetPool{
		rows: make([]*gtk.ListBoxRow, 0),
	}
}

// GetOrCreateRow returns an existing row or creates a new one if needed
func (wp *WidgetPool) GetOrCreateRow() *gtk.ListBoxRow {
	wp.mu.Lock()
	defer wp.mu.Unlock()

	if len(wp.rows) > 0 {
		// Return the last row from pool
		row := wp.rows[len(wp.rows)-1]
		wp.rows = wp.rows[:len(wp.rows)-1]
		return row
	}

	// Create new row if pool is empty
	row, err := gtk.ListBoxRowNew()
	if err != nil {
		return nil
	}
	return row
}

// ReturnRow puts a row back into the pool for reuse
func (wp *WidgetPool) ReturnRow(row *gtk.ListBoxRow) {
	if row == nil {
		return
	}

	wp.mu.Lock()
	defer wp.mu.Unlock()

	// Hide the row before returning to pool
	row.Hide()
	wp.rows = append(wp.rows, row)
}

// Clear empties the pool and destroys all widgets
func (wp *WidgetPool) Clear() {
	wp.mu.Lock()
	defer wp.mu.Unlock()

	// Note: In GTK3, widgets are automatically destroyed
	// when their parent is destroyed, so we don't need to manually destroy them
	wp.rows = wp.rows[:0]
}

// Size returns the current pool size
func (wp *WidgetPool) Size() int {
	wp.mu.Lock()
	defer wp.mu.Unlock()
	return len(wp.rows)
}
