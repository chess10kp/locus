package launcher

import (
	"context"
	"testing"
	"time"

	"github.com/chess10kp/locus/internal/config"
)

// MockHook is a test hook implementation
type MockHook struct {
	id       string
	priority int
	onSelect func(execCtx context.Context, ctx *HookContext, data ActionData) HookResult
	onEnter  func(execCtx context.Context, ctx *HookContext, text string) HookResult
	onTab    func(execCtx context.Context, ctx *HookContext, text string) TabResult
}

func (h *MockHook) ID() string {
	return h.id
}

func (h *MockHook) Priority() int {
	return h.priority
}

func (h *MockHook) OnSelect(execCtx context.Context, ctx *HookContext, data ActionData) HookResult {
	if h.onSelect != nil {
		return h.onSelect(execCtx, ctx, data)
	}
	return HookResult{Handled: false}
}

func (h *MockHook) OnEnter(execCtx context.Context, ctx *HookContext, text string) HookResult {
	if h.onEnter != nil {
		return h.onEnter(execCtx, ctx, text)
	}
	return HookResult{Handled: false}
}

func (h *MockHook) OnTab(execCtx context.Context, ctx *HookContext, text string) TabResult {
	if h.onTab != nil {
		return h.onTab(execCtx, ctx, text)
	}
	return TabResult{Handled: false}
}

func (h *MockHook) Cleanup() {
	// No-op for testing
}

func TestHookRegistryRegister(t *testing.T) {
	registry := NewHookRegistry()

	hook1 := &MockHook{id: "hook1", priority: 10}
	hook2 := &MockHook{id: "hook2", priority: 5}

	// Register hooks
	err := registry.Register("timer", hook1)
	if err != nil {
		t.Fatalf("Failed to register hook1: %v", err)
	}

	err = registry.Register("timer", hook2)
	if err != nil {
		t.Fatalf("Failed to register hook2: %v", err)
	}

	// Check hooks are registered in priority order
	hooks := registry.GetHooks("timer")
	if len(hooks) != 2 {
		t.Fatalf("Expected 2 hooks, got %d", len(hooks))
	}

	// hook2 should come first (lower priority number)
	if hooks[0].ID() != "hook2" {
		t.Errorf("Expected hook2 first, got %s", hooks[0].ID())
	}

	if hooks[1].ID() != "hook1" {
		t.Errorf("Expected hook1 second, got %s", hooks[1].ID())
	}
}

func TestHookRegistryDuplicateRegistration(t *testing.T) {
	registry := NewHookRegistry()

	hook1 := &MockHook{id: "hook1", priority: 10}
	hook2 := &MockHook{id: "hook1", priority: 5} // Same ID

	err := registry.Register("timer", hook1)
	if err != nil {
		t.Fatalf("Failed to register hook1: %v", err)
	}

	err = registry.Register("timer", hook2)
	if err == nil {
		t.Error("Expected error for duplicate hook ID, got none")
	}
}

func TestHookRegistryUnregister(t *testing.T) {
	registry := NewHookRegistry()

	hook := &MockHook{id: "hook1", priority: 10}
	registry.Register("timer", hook)

	hooks := registry.GetHooks("timer")
	if len(hooks) != 1 {
		t.Fatalf("Expected 1 hook, got %d", len(hooks))
	}

	registry.Unregister("timer", "hook1")

	hooks = registry.GetHooks("timer")
	if len(hooks) != 0 {
		t.Errorf("Expected 0 hooks after unregister, got %d", len(hooks))
	}
}

func TestHookRegistryExecuteSelectHooks(t *testing.T) {
	registry := NewHookRegistry()

	// Hook that doesn't handle but stops propagation (highest priority)
	stoppingHook := &MockHook{
		id:       "stopping",
		priority: 5,
		onSelect: func(execCtx context.Context, ctx *HookContext, data ActionData) HookResult {
			return HookResult{Handled: false, StopPropagation: true}
		},
	}

	// Hook that handles the event (lower priority - executes after stopping hook)
	handlingHook := &MockHook{
		id:       "handling",
		priority: 10,
		onSelect: func(execCtx context.Context, ctx *HookContext, data ActionData) HookResult {
			return HookResult{Handled: true}
		},
	}

	// Hook that doesn't handle
	nonHandlingHook := &MockHook{
		id:       "non-handling",
		priority: 15,
		onSelect: func(execCtx context.Context, ctx *HookContext, data ActionData) HookResult {
			return HookResult{Handled: false}
		},
	}

	registry.Register("test", stoppingHook)
	registry.Register("test", handlingHook)
	registry.Register("test", nonHandlingHook)

	refreshUICh := make(chan RefreshUIRequest, 1)
	statusCh := make(chan StatusRequest, 1)
	ctx := &HookContext{
		LauncherName: "test",
		Config:       &config.Config{},
		RefreshUI:    refreshUICh,
		SendStatus:   statusCh,
	}

	action := NewShellAction("echo test")
	result := registry.ExecuteSelectHooks(context.Background(), ctx, action)

	// The stopping hook should prevent the handling hook from executing
	if result.Handled {
		t.Error("Expected event not to be handled due to StopPropagation")
	}

	if !result.StopPropagation {
		t.Error("Expected StopPropagation to be true")
	}
}

func TestHookRegistryExecuteEnterHooks(t *testing.T) {
	registry := NewHookRegistry()

	hook := &MockHook{
		id:       "enter-hook",
		priority: 10,
		onEnter: func(execCtx context.Context, ctx *HookContext, text string) HookResult {
			return HookResult{Handled: true}
		},
	}

	registry.Register("timer", hook)

	refreshUICh := make(chan RefreshUIRequest, 1)
	statusCh := make(chan StatusRequest, 1)
	ctx := &HookContext{
		LauncherName: "timer",
		Config:       &config.Config{},
		RefreshUI:    refreshUICh,
		SendStatus:   statusCh,
	}

	result := registry.ExecuteEnterHooks(context.Background(), ctx, "test command")

	if !result.Handled {
		t.Error("Hook was not executed")
	}
}

func TestHookRegistryExecuteTabHooks(t *testing.T) {
	registry := NewHookRegistry()

	hook := &MockHook{
		id:       "tab-hook",
		priority: 10,
		onTab: func(execCtx context.Context, ctx *HookContext, text string) TabResult {
			return TabResult{NewText: ">timer ", Handled: true}
		},
	}

	registry.Register("timer", hook)

	refreshUICh := make(chan RefreshUIRequest, 1)
	statusCh := make(chan StatusRequest, 1)
	ctx := &HookContext{
		LauncherName: "timer",
		Config:       &config.Config{},
		RefreshUI:    refreshUICh,
		SendStatus:   statusCh,
	}

	result := registry.ExecuteTabHooks(context.Background(), ctx, ">timer")

	if !result.Handled {
		t.Error("Expected tab completion to be handled")
	}

	if result.NewText != ">timer " {
		t.Errorf("Expected new text '>timer ', got '%s'", result.NewText)
	}
}

func TestHookStats(t *testing.T) {
	stats := NewHookStats()

	stats.RecordExecution(time.Millisecond*100, true)
	stats.RecordExecution(time.Millisecond*200, true)
	stats.RecordExecution(time.Millisecond*50, false)

	currentStats := stats.GetStats()

	if currentStats.TotalExecutions != 3 {
		t.Errorf("Expected 3 total executions, got %d", currentStats.TotalExecutions)
	}

	if currentStats.SuccessfulExecutions != 2 {
		t.Errorf("Expected 2 successful executions, got %d", currentStats.SuccessfulExecutions)
	}

	if currentStats.FailedExecutions != 1 {
		t.Errorf("Expected 1 failed execution, got %d", currentStats.FailedExecutions)
	}

	// Average should be around 116ms (weighted average)
	if currentStats.AverageExecutionTime < time.Millisecond*100 ||
		currentStats.AverageExecutionTime > time.Millisecond*130 {
		t.Errorf("Expected average execution time around 116ms, got %v", currentStats.AverageExecutionTime)
	}
}

func TestHookRegistryCleanup(t *testing.T) {
	registry := NewHookRegistry()

	hook1 := &MockHook{id: "hook1", priority: 10}
	hook2 := &MockHook{id: "hook2", priority: 5}

	registry.Register("timer", hook1)
	registry.Register("clipboard", hook2)

	if len(registry.GetHooks("timer")) != 1 {
		t.Error("Expected 1 hook for timer")
	}

	if len(registry.GetHooks("clipboard")) != 1 {
		t.Error("Expected 1 hook for clipboard")
	}

	registry.Cleanup()

	if len(registry.GetHooks("timer")) != 0 {
		t.Error("Expected 0 hooks for timer after cleanup")
	}

	if len(registry.GetHooks("clipboard")) != 0 {
		t.Error("Expected 0 hooks for clipboard after cleanup")
	}
}

// TestHookContext tests the HookContext structure
func TestHookContext(t *testing.T) {
	refreshUICh := make(chan RefreshUIRequest, 1)
	statusCh := make(chan StatusRequest, 1)
	ctx := &HookContext{
		LauncherName: "timer",
		Query:        "5m",
		Config:       &config.Config{},
		RefreshUI:    refreshUICh,
		SendStatus:   statusCh,
	}

	if ctx.LauncherName != "timer" {
		t.Errorf("Expected launcher name 'timer', got '%s'", ctx.LauncherName)
	}

	if ctx.Query != "5m" {
		t.Errorf("Expected query '5m', got '%s'", ctx.Query)
	}

	if ctx.RefreshUI == nil {
		t.Error("RefreshUI callback should not be nil")
	}

	if ctx.SendStatus == nil {
		t.Error("SendStatus callback should not be nil")
	}
}
