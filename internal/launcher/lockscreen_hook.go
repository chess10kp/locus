package launcher

import (
	"context"
	"log"
)

// LockScreenHook handles lock screen actions
type LockScreenHook struct {
	callback func() error
}

func NewLockScreenHook(callback func() error) *LockScreenHook {
	return &LockScreenHook{
		callback: callback,
	}
}

func (h *LockScreenHook) ID() string {
	return "lock-screen-hook"
}

func (h *LockScreenHook) Priority() int {
	return 100 // High priority to handle lock screen first
}

func (h *LockScreenHook) OnSelect(execCtx context.Context, ctx *HookContext, data ActionData) HookResult {
	// Check if this is a lock screen action
	if data.Type() == "lock_screen" {
		log.Println("[LOCK-SCREEN-HOOK] Handling lock screen action")

		// Show lock screen via callback
		if err := h.callback(); err != nil {
			log.Printf("[LOCK-SCREEN-HOOK] Failed to show lock screen: %v", err)
			return HookResult{
				Error:   err,
				Handled: true,
			}
		}

		return HookResult{
			Handled: true,
		}
	}

	return HookResult{
		Handled: false,
	}
}

func (h *LockScreenHook) OnEnter(execCtx context.Context, ctx *HookContext, text string) HookResult {
	return HookResult{Handled: false}
}

func (h *LockScreenHook) OnTab(execCtx context.Context, ctx *HookContext, text string) TabResult {
	return TabResult{Handled: false}
}

func (h *LockScreenHook) Cleanup() {
}
