package statusbar

import (
	"log"
	"sync"
	"time"

	"github.com/gotk3/gotk3/glib"
	"github.com/gotk3/gotk3/gtk"
)

// AsyncWidgetUpdate handles updating a widget asynchronously
// It runs the data fetch in a goroutine and updates the widget in the UI thread
type AsyncWidgetUpdate struct {
	module     string
	widget     gtk.IWidget
	fetchFunc  func() (interface{}, error)
	updateFunc func(gtk.IWidget, interface{}) error
	mu         sync.Mutex
	running    bool
}

// NewAsyncWidgetUpdate creates a new async widget updater
func NewAsyncWidgetUpdate(
	moduleName string,
	widget gtk.IWidget,
	fetchFunc func() (interface{}, error),
	updateFunc func(gtk.IWidget, interface{}) error,
) *AsyncWidgetUpdate {
	return &AsyncWidgetUpdate{
		module:     moduleName,
		widget:     widget,
		fetchFunc:  fetchFunc,
		updateFunc: updateFunc,
		running:    true,
	}
}

// Update performs an async update
func (a *AsyncWidgetUpdate) Update() {
	a.mu.Lock()
	if !a.running {
		a.mu.Unlock()
		return
	}
	a.mu.Unlock()

	go a.fetchAndUpdate()
}

// fetchAndUpdate fetches data in background and updates widget in UI thread
func (a *AsyncWidgetUpdate) fetchAndUpdate() {
	startTime := time.Now()

	// Fetch data in goroutine (not blocking UI thread)
	data, err := a.fetchFunc()

	// Update widget in UI thread
	glib.IdleAdd(func() {
		a.mu.Lock()
		if !a.running {
			a.mu.Unlock()
			return
		}
		a.mu.Unlock()

		updateStart := time.Now()
		log.Printf("[ASYNC-UPDATE] Updating widget for module '%s' (fetch took %v)",
			a.module, updateStart.Sub(startTime))

		if err != nil {
			log.Printf("[ASYNC-UPDATE] Failed to fetch data for module '%s': %v", a.module, err)
			return
		}

		if a.widget != nil {
			if err := a.updateFunc(a.widget, data); err != nil {
				log.Printf("[ASYNC-UPDATE] Failed to update widget for module '%s': %v", a.module, err)
			}
		}

		log.Printf("[ASYNC-UPDATE] Widget update for '%s' completed in %v (total: %v)",
			a.module, time.Since(updateStart), time.Since(startTime))
	})
}

// Stop stops the async updater
func (a *AsyncWidgetUpdate) Stop() {
	a.mu.Lock()
	a.running = false
	a.mu.Unlock()
}

// AsyncCommandHelper helps with running commands asynchronously
type AsyncCommandHelper struct {
	module  string
	timeout time.Duration
}

// NewAsyncCommandHelper creates a new async command helper
func NewAsyncCommandHelper(moduleName string, timeout time.Duration) *AsyncCommandHelper {
	return &AsyncCommandHelper{
		module:  moduleName,
		timeout: timeout,
	}
}

// RunCommand runs a command asynchronously and returns the result via callback
func (h *AsyncCommandHelper) RunCommand(
	name string,
	args []string,
	callback func(output []byte, err error),
) {
	go func() {
		startTime := time.Now()
		log.Printf("[ASYNC-CMD] Module '%s' starting command: %s", h.module, name)

		// TODO: Implement actual command execution with timeout
		// This is a placeholder for the actual implementation

		log.Printf("[ASYNC-CMD] Module '%s' command completed in %v", h.module, time.Since(startTime))
	}()
}

// ModuleWithAsyncUpdate is a helper interface for modules that support async updates
type ModuleWithAsyncUpdate interface {
	GetAsyncWidgetUpdate() *AsyncWidgetUpdate
}

// WrapUpdateWidget wraps a module's UpdateWidget to be non-blocking
// This is a helper for modules that need to be converted to async
func WrapUpdateWidget(
	moduleName string,
	updateFunc func(gtk.IWidget) error,
	widget gtk.IWidget,
) {
	startTime := time.Now()

	// If update takes longer than 100ms, log a warning
	done := make(chan struct{})
	go func() {
		defer func() {
			if r := recover(); r != nil {
				log.Printf("[ASYNC-WRAPPER] Panic in update for '%s': %v", moduleName, r)
			}
		}()

		if err := updateFunc(widget); err != nil {
			log.Printf("[ASYNC-WRAPPER] Update failed for '%s': %v", moduleName, err)
		}
		close(done)
	}()

	// Log if update takes too long
	select {
	case <-done:
		duration := time.Since(startTime)
		if duration > 100*time.Millisecond {
			log.Printf("[ASYNC-WRAPPER] WARNING: Update for '%s' took %v (slow!)", moduleName, duration)
		}
	case <-time.After(5 * time.Second):
		log.Printf("[ASYNC-WRAPPER] CRITICAL: Update for '%s' BLOCKED for >5s - module is blocking UI thread!", moduleName)
	}
}
