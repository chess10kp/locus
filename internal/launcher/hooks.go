package launcher

import (
	"context"
	"fmt"
	"log"
	"sort"
	"sync"
	"time"

	"github.com/sigma/locus-go/internal/config"
)

// HookContext provides context information to hooks during execution
type HookContext struct {
	LauncherName string
	Query        string
	SelectedItem *LauncherItem
	Config       *config.Config
	RefreshUI    chan<- RefreshUIRequest // Channel to request UI refresh
	SendStatus   chan<- StatusRequest    // Channel to send status messages
}

// RefreshUI sends a request to refresh the UI
func (ctx *HookContext) RefreshUIAsync() <-chan error {
	responseCh := make(chan error, 1)
	select {
	case ctx.RefreshUI <- RefreshUIRequest{Response: responseCh}:
		return responseCh
	default:
		// Channel full, return error immediately
		responseCh <- fmt.Errorf("refresh UI request queue full")
		close(responseCh)
		return responseCh
	}
}

// SendStatusAsync sends a status message asynchronously
func (ctx *HookContext) SendStatusAsync(msg string) <-chan error {
	responseCh := make(chan error, 1)
	select {
	case ctx.SendStatus <- StatusRequest{Message: msg, Response: responseCh}:
		return responseCh
	default:
		// Channel full, return error immediately
		responseCh <- fmt.Errorf("status request queue full")
		close(responseCh)
		return responseCh
	}
}

// RefreshUIRequest is sent to request a UI refresh
type RefreshUIRequest struct {
	Response chan<- error
}

// StatusRequest is sent to request a status message
type StatusRequest struct {
	Message  string
	Response chan<- error
}

// HookResult represents the result of hook execution
type HookResult struct {
	Handled         bool        // Whether the hook handled the event
	StopPropagation bool        // Whether to stop executing other hooks
	Error           error       // Error that occurred during execution
	ModifiedData    interface{} // Modified data to pass to next hooks or execution
}

// TabResult represents the result of tab completion hook execution
type TabResult struct {
	NewText string // The new text to set in the input field
	Handled bool   // Whether the hook handled the tab completion
}

// Hook defines the interface for launcher hooks
type Hook interface {
	ID() string    // Unique identifier for the hook
	Priority() int // Lower values = higher priority (executed first)
	OnSelect(execCtx context.Context, ctx *HookContext, data ActionData) HookResult
	OnEnter(execCtx context.Context, ctx *HookContext, text string) HookResult
	OnTab(execCtx context.Context, ctx *HookContext, text string) TabResult
	Cleanup() // Called when the hook is being removed
}

// AsyncHook extends Hook with async execution capabilities
type AsyncHook interface {
	Hook
	OnSelectAsync(ctx *HookContext, data ActionData) <-chan HookResult
	OnEnterAsync(ctx *HookContext, text string) <-chan HookResult
	OnTabAsync(ctx *HookContext, text string) <-chan TabResult
}

// HookStats tracks hook execution statistics
type HookStats struct {
	TotalExecutions      int64
	SuccessfulExecutions int64
	FailedExecutions     int64
	AverageExecutionTime time.Duration
	mu                   sync.RWMutex
}

// NewHookStats creates a new HookStats instance
func NewHookStats() *HookStats {
	return &HookStats{}
}

// RecordExecution records a hook execution result
func (s *HookStats) RecordExecution(duration time.Duration, success bool) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.TotalExecutions++
	if success {
		s.SuccessfulExecutions++
	} else {
		s.FailedExecutions++
	}

	// Simple moving average for execution time
	if s.TotalExecutions == 1 {
		s.AverageExecutionTime = duration
	} else {
		// Weighted average favoring recent executions
		// Use float64 to prevent int64 overflow
		currentAvg := float64(s.AverageExecutionTime)
		newDuration := float64(duration)
		s.AverageExecutionTime = time.Duration((currentAvg*0.99 + newDuration*0.01))
	}
}

// GetStats returns a copy of the current stats
func (s *HookStats) GetStats() HookStats {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return HookStats{
		TotalExecutions:      s.TotalExecutions,
		SuccessfulExecutions: s.SuccessfulExecutions,
		FailedExecutions:     s.FailedExecutions,
		AverageExecutionTime: s.AverageExecutionTime,
	}
}

// HookRegistry manages hooks for all launchers
type HookRegistry struct {
	hooks         map[string][]Hook // launcherName -> sorted hooks
	stats         *HookStats
	asyncExecutor *AsyncExecutor
	mu            sync.RWMutex
}

// AsyncExecutor manages a pool of goroutines for async operations
type AsyncExecutor struct {
	sem chan struct{}
}

// NewAsyncExecutor creates a new AsyncExecutor with the specified max concurrency
func NewAsyncExecutor(maxConcurrency int) *AsyncExecutor {
	return &AsyncExecutor{
		sem: make(chan struct{}, maxConcurrency),
	}
}

// Execute runs a function in the pool, blocking if pool is full
func (e *AsyncExecutor) Execute(fn func()) {
	e.sem <- struct{}{} // Acquire
	go func() {
		defer func() { <-e.sem }() // Release
		fn()
	}()
}

// ExecuteWithTimeout runs a function with timeout
func (e *AsyncExecutor) ExecuteWithTimeout(fn func(), timeout time.Duration) error {
	select {
	case e.sem <- struct{}{}: // Acquire
		go func() {
			defer func() { <-e.sem }() // Release
			fn()
		}()
		return nil
	case <-time.After(timeout):
		return fmt.Errorf("async executor queue full, timeout after %v", timeout)
	}
}

// NewHookRegistry creates a new HookRegistry
func NewHookRegistry() *HookRegistry {
	return &HookRegistry{
		hooks:         make(map[string][]Hook),
		stats:         NewHookStats(),
		asyncExecutor: NewAsyncExecutor(10), // Max 10 concurrent async hooks
	}
}

// Register registers a hook for a launcher
func (r *HookRegistry) Register(launcherName string, hook Hook) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	// Check for duplicate hook ID
	for _, existingHook := range r.hooks[launcherName] {
		if existingHook.ID() == hook.ID() {
			return fmt.Errorf("hook with ID '%s' already registered for launcher '%s'", hook.ID(), launcherName)
		}
	}

	r.hooks[launcherName] = append(r.hooks[launcherName], hook)
	r.sortHooks(launcherName)

	log.Printf("[HOOK-REGISTRY] Registered hook '%s' for launcher '%s'", hook.ID(), launcherName)
	return nil
}

// Unregister removes a hook from a launcher
func (r *HookRegistry) Unregister(launcherName, hookID string) {
	r.mu.Lock()
	defer r.mu.Unlock()

	hooks := r.hooks[launcherName]
	for i, hook := range hooks {
		if hook.ID() == hookID {
			// Remove hook from slice first
			r.hooks[launcherName] = append(hooks[:i], hooks[i+1:]...)

			// Unlock before cleanup to prevent deadlocks
			r.mu.Unlock()
			hook.Cleanup()
			r.mu.Lock() // Re-lock for consistency

			log.Printf("[HOOK-REGISTRY] Unregistered hook '%s' from launcher '%s'", hookID, launcherName)
			return
		}
	}
}

// UnregisterAll removes all hooks for a launcher
func (r *HookRegistry) UnregisterAll(launcherName string) {
	r.mu.Lock()
	defer r.mu.Unlock()

	hooks := r.hooks[launcherName]
	for _, hook := range hooks {
		hook.Cleanup()
	}

	delete(r.hooks, launcherName)
	log.Printf("[HOOK-REGISTRY] Unregistered all hooks for launcher '%s'", launcherName)
}

// GetHooks returns all hooks for a launcher (for testing/debugging)
func (r *HookRegistry) GetHooks(launcherName string) []Hook {
	r.mu.RLock()
	defer r.mu.RUnlock()

	hooks := r.hooks[launcherName]
	result := make([]Hook, len(hooks))
	copy(result, hooks)
	return result
}

// ExecuteSelectHooks executes all OnSelect hooks for a launcher
func (r *HookRegistry) ExecuteSelectHooks(execCtx context.Context, ctx *HookContext, data ActionData) HookResult {
	start := time.Now()
	defer func() {
		duration := time.Since(start)
		success := recover() == nil
		r.stats.RecordExecution(duration, success)
	}()

	r.mu.RLock()
	hooks := r.hooks[ctx.LauncherName]
	r.mu.RUnlock()

	for _, hook := range hooks {
		result, err := r.executeSingleHookSelect(execCtx, hook, ctx, data)
		if err != nil {
			log.Printf("[HOOK-REGISTRY] Error executing OnSelect hook '%s': %v", hook.ID(), err)
			continue
		}

		if result.Handled {
			log.Printf("[HOOK-REGISTRY] Hook '%s' handled OnSelect event", hook.ID())
			return result
		}

		if result.StopPropagation {
			log.Printf("[HOOK-REGISTRY] Hook '%s' stopped OnSelect propagation", hook.ID())
			return result
		}

		// Update data for next hook if modified
		if result.ModifiedData != nil {
			if newData, ok := result.ModifiedData.(ActionData); ok {
				data = newData
			}
		}
	}

	return HookResult{Handled: false}
}

// executeSingleHookSelect executes a single hook and recovers from panics
func (r *HookRegistry) executeSingleHookSelect(execCtx context.Context, hook Hook, ctx *HookContext, data ActionData) (HookResult, error) {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("[HOOK-REGISTRY] Panic in OnSelect hook '%s': %v", hook.ID(), r)
		}
	}()

	result := hook.OnSelect(execCtx, ctx, data)
	return result, nil
}

// ExecuteEnterHooks executes all OnEnter hooks for a launcher
func (r *HookRegistry) ExecuteEnterHooks(execCtx context.Context, ctx *HookContext, text string) HookResult {
	start := time.Now()
	defer func() {
		duration := time.Since(start)
		success := recover() == nil
		r.stats.RecordExecution(duration, success)
	}()

	r.mu.RLock()
	hooks := r.hooks[ctx.LauncherName]
	r.mu.RUnlock()

	for _, hook := range hooks {
		result, err := r.executeSingleHookEnter(execCtx, hook, ctx, text)
		if err != nil {
			log.Printf("[HOOK-REGISTRY] Error executing OnEnter hook '%s': %v", hook.ID(), err)
			continue
		}

		if result.Handled {
			log.Printf("[HOOK-REGISTRY] Hook '%s' handled OnEnter event", hook.ID())
			return result
		}

		if result.StopPropagation {
			log.Printf("[HOOK-REGISTRY] Hook '%s' stopped OnEnter propagation", hook.ID())
			return result
		}
	}

	return HookResult{Handled: false}
}

// executeSingleHookEnter executes a single hook and recovers from panics
func (r *HookRegistry) executeSingleHookEnter(execCtx context.Context, hook Hook, ctx *HookContext, text string) (HookResult, error) {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("[HOOK-REGISTRY] Panic in OnEnter hook '%s': %v", hook.ID(), r)
		}
	}()

	log.Printf("[HOOK-REGISTRY] Executing OnEnter hook '%s' for launcher '%s'", hook.ID(), ctx.LauncherName)
	result := hook.OnEnter(execCtx, ctx, text)
	return result, nil
}

// ExecuteTabHooks executes all OnTab hooks for a launcher
func (r *HookRegistry) ExecuteTabHooks(execCtx context.Context, ctx *HookContext, text string) TabResult {
	start := time.Now()
	defer func() {
		duration := time.Since(start)
		success := recover() == nil
		r.stats.RecordExecution(duration, success)
	}()

	r.mu.RLock()
	hooks := r.hooks[ctx.LauncherName]
	r.mu.RUnlock()

	for _, hook := range hooks {
		result, err := r.executeSingleHookTab(execCtx, hook, ctx, text)
		if err != nil {
			log.Printf("[HOOK-REGISTRY] Error executing OnTab hook '%s': %v", hook.ID(), err)
			continue
		}

		if result.Handled {
			log.Printf("[HOOK-REGISTRY] Hook '%s' handled OnTab event with text: '%s'", hook.ID(), result.NewText)
			return result
		}
	}

	return TabResult{Handled: false}
}

// executeSingleHookTab executes a single hook and recovers from panics
func (r *HookRegistry) executeSingleHookTab(execCtx context.Context, hook Hook, ctx *HookContext, text string) (TabResult, error) {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("[HOOK-REGISTRY] Panic in OnTab hook '%s': %v", hook.ID(), r)
		}
	}()

	log.Printf("[HOOK-REGISTRY] Executing OnTab hook '%s' for launcher '%s'", hook.ID(), ctx.LauncherName)
	result := hook.OnTab(execCtx, ctx, text)
	return result, nil
}

// ExecuteSelectHooksAsync executes all OnSelect hooks asynchronously
func (r *HookRegistry) ExecuteSelectHooksAsync(ctx *HookContext, data ActionData, timeout time.Duration) HookResult {
	r.mu.RLock()
	hooks := r.hooks[ctx.LauncherName]
	r.mu.RUnlock()

	if len(hooks) == 0 {
		return HookResult{Handled: false}
	}

	// Check if any hooks support async execution
	asyncHooks := make([]AsyncHook, 0)
	for _, hook := range hooks {
		if asyncHook, ok := hook.(AsyncHook); ok {
			asyncHooks = append(asyncHooks, asyncHook)
		}
	}

	if len(asyncHooks) == 0 {
		// Fall back to synchronous execution
		return r.ExecuteSelectHooks(context.Background(), ctx, data)
	}

	// Execute async hooks using the executor pool
	type resultWithHook struct {
		result HookResult
		hook   Hook
	}

	results := make(chan resultWithHook, len(asyncHooks))
	ctxTimeout, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	// Start all async hooks
	for _, hook := range asyncHooks {
		h := hook // Capture loop variable
		err := r.asyncExecutor.ExecuteWithTimeout(func() {
			defer func() {
				if r := recover(); r != nil {
					log.Printf("[HOOK-REGISTRY] Panic in async OnSelect hook '%s': %v", h.ID(), r)
					select {
					case results <- resultWithHook{
						result: HookResult{Error: fmt.Errorf("panic: %v", r)},
						hook:   h,
					}:
					case <-ctxTimeout.Done():
					}
				}
			}()

			select {
			case result := <-h.OnSelectAsync(ctx, data):
				select {
				case results <- resultWithHook{result: result, hook: h}:
				case <-ctxTimeout.Done():
				}
			case <-ctxTimeout.Done():
				select {
				case results <- resultWithHook{
					result: HookResult{Error: fmt.Errorf("timeout after %v", timeout)},
					hook:   h,
				}:
				default:
				}
			}
		}, timeout)

		if err != nil {
			// Executor queue full, log and continue
			log.Printf("[HOOK-REGISTRY] Failed to execute async hook '%s': %v", h.ID(), err)
		}
	}

	// Collect results with timeout
	collected := 0
	for collected < len(asyncHooks) {
		select {
		case result := <-results:
			collected++
			if result.result.Handled {
				return result.result
			}
			if result.result.StopPropagation {
				return result.result
			}
		case <-ctxTimeout.Done():
			log.Printf("[HOOK-REGISTRY] Async hook execution timed out after %v", timeout)
			return HookResult{Error: fmt.Errorf("async execution timeout")}
		}
	}

	return HookResult{Handled: false}
}

// sortHooks sorts hooks by priority (lower priority value = higher priority)
func (r *HookRegistry) sortHooks(launcherName string) {
	hooks := r.hooks[launcherName]
	sort.Slice(hooks, func(i, j int) bool {
		return hooks[i].Priority() < hooks[j].Priority()
	})
}

// GetStats returns hook execution statistics
func (r *HookRegistry) GetStats() HookStats {
	return r.stats.GetStats()
}

// Cleanup cleans up all hooks
func (r *HookRegistry) Cleanup() {
	r.mu.Lock()
	defer r.mu.Unlock()

	for launcherName, hooks := range r.hooks {
		for _, hook := range hooks {
			hook.Cleanup()
		}
		log.Printf("[HOOK-REGISTRY] Cleaned up %d hooks for launcher '%s'", len(hooks), launcherName)
	}

	r.hooks = make(map[string][]Hook)
	log.Printf("[HOOK-REGISTRY] Hook registry cleaned up")
}
