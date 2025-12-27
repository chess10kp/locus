package statusbar

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/gotk3/gotk3/gtk"
)

// ModuleUpdateInfo stores update information for a module
type ModuleUpdateInfo struct {
	Module    Module
	Widget    gtk.IWidget
	Timer     *time.Timer
	Listeners []EventListener
	Active    bool
}

// UpdateScheduler manages module updates based on their update modes
type UpdateScheduler struct {
	registry       *ModuleRegistry
	updates        map[string]*ModuleUpdateInfo
	periodicTicker *time.Ticker
	ctx            context.Context
	cancel         context.CancelFunc
	mu             sync.RWMutex
	widgetMap      map[string]gtk.IWidget
	running        bool
	callbacks      map[string]func()
}

// NewUpdateScheduler creates a new update scheduler
func NewUpdateScheduler(registry *ModuleRegistry) *UpdateScheduler {
	ctx, cancel := context.WithCancel(context.Background())
	return &UpdateScheduler{
		registry:  registry,
		updates:   make(map[string]*ModuleUpdateInfo),
		ctx:       ctx,
		cancel:    cancel,
		widgetMap: make(map[string]gtk.IWidget),
		running:   false,
		callbacks: make(map[string]func()),
	}
}

// Start starts the update scheduler
func (s *UpdateScheduler) Start() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.running {
		return fmt.Errorf("scheduler is already running")
	}

	s.periodicTicker = time.NewTicker(1 * time.Second)
	s.running = true

	go s.run()

	log.Printf("Update scheduler started")

	return nil
}

// Stop stops the update scheduler
func (s *UpdateScheduler) Stop() {
	s.mu.Lock()
	defer s.mu.Unlock()

	if !s.running {
		return
	}

	s.cancel()
	s.running = false

	if s.periodicTicker != nil {
		s.periodicTicker.Stop()
	}

	s.cleanupAllUpdates()

	log.Printf("Update scheduler stopped")
}

// ScheduleModule schedules updates for a module
func (s *UpdateScheduler) ScheduleModule(name string, widget gtk.IWidget) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	module, exists := s.registry.GetModule(name)
	if !exists {
		return fmt.Errorf("module '%s' not found", name)
	}

	if _, exists := s.updates[name]; exists {
		return fmt.Errorf("module '%s' is already scheduled", name)
	}

	info := &ModuleUpdateInfo{
		Module: module,
		Widget: widget,
		Active: false,
	}

	switch module.UpdateMode() {
	case UpdateModePeriodic:
		s.schedulePeriodic(name, info)
	case UpdateModeEventDriven:
		s.scheduleEventDriven(name, info)
	case UpdateModeStatic, UpdateModeOnDemand:
		info.Active = true
	default:
		return fmt.Errorf("unsupported update mode: %v", module.UpdateMode())
	}

	s.updates[name] = info
	s.widgetMap[name] = widget

	log.Printf("Scheduled module '%s' with update mode: %v", name, module.UpdateMode())

	return nil
}

// schedulePeriodic schedules a periodic module update
func (s *UpdateScheduler) schedulePeriodic(name string, info *ModuleUpdateInfo) {
	interval := info.Module.UpdateInterval()
	if interval == 0 {
		interval = time.Second
	}

	info.Timer = time.NewTimer(interval)
	info.Active = true

	go func() {
		defer func() {
			if r := recover(); r != nil {
				log.Printf("Recovered from panic in periodic update for '%s': %v", name, r)
			}
		}()

		for {
			select {
			case <-s.ctx.Done():
				return
			case <-info.Timer.C:
				s.updateModule(name)

				if info.Timer == nil {
					return
				}
				info.Timer.Reset(interval)
			}
		}
	}()
}

// scheduleEventDriven schedules an event-driven module update
func (s *UpdateScheduler) scheduleEventDriven(name string, info *ModuleUpdateInfo) {
	callback := func() {
		s.updateModule(name)
	}

	s.callbacks[name] = callback

	if err := s.registry.SetupModuleEventListeners(name); err != nil {
		log.Printf("Failed to setup event listeners for module '%s': %v", name, err)
		return
	}

	info.Active = true

	if err := s.registry.StartModuleListeners(name, callback); err != nil {
		log.Printf("Failed to start listeners for module '%s': %v", name, err)
		return
	}
}

// UnscheduleModule removes a module from the scheduler
func (s *UpdateScheduler) UnscheduleModule(name string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	info, exists := s.updates[name]
	if !exists {
		return
	}

	if info.Timer != nil {
		info.Timer.Stop()
		info.Timer = nil
	}

	if len(info.Listeners) > 0 {
		for _, listener := range info.Listeners {
			listener.Stop()
		}
	}

	if _, ok := s.callbacks[name]; ok {
		s.registry.StopModuleListeners(name)
		delete(s.callbacks, name)
	}

	info.Active = false
	delete(s.updates, name)
	delete(s.widgetMap, name)

	log.Printf("Unscheduled module '%s'", name)
}

// UpdateModule immediately updates a module
func (s *UpdateScheduler) UpdateModule(name string) error {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return s.updateModule(name)
}

// updateModule updates a module's widget
func (s *UpdateScheduler) updateModule(name string) error {
	widget, ok := s.widgetMap[name]
	if !ok {
		return fmt.Errorf("widget not found for module '%s'", name)
	}

	return s.registry.UpdateModuleWidget(name, widget)
}

// UpdateAll updates all scheduled modules
func (s *UpdateScheduler) UpdateAll() {
	s.mu.RLock()
	defer s.mu.RUnlock()

	for name := range s.updates {
		if err := s.updateModule(name); err != nil {
			log.Printf("Failed to update module '%s': %v", name, err)
		}
	}
}

// UpdateModulesByMode updates all modules with a specific update mode
func (s *UpdateScheduler) UpdateModulesByMode(mode UpdateMode) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	for name, info := range s.updates {
		if info.Module.UpdateMode() == mode {
			if err := s.updateModule(name); err != nil {
				log.Printf("Failed to update module '%s': %v", name, err)
			}
		}
	}
}

// IsScheduled checks if a module is scheduled
func (s *UpdateScheduler) IsScheduled(name string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	_, exists := s.updates[name]
	return exists
}

// GetScheduledModules returns all scheduled module names
func (s *UpdateScheduler) GetScheduledModules() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	names := make([]string, 0, len(s.updates))
	for name := range s.updates {
		names = append(names, name)
	}

	return names
}

// GetModuleWidget returns a module's widget
func (s *UpdateScheduler) GetModuleWidget(name string) (gtk.IWidget, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	widget, exists := s.widgetMap[name]
	return widget, exists
}

// SetModuleWidget sets a module's widget
func (s *UpdateScheduler) SetModuleWidget(name string, widget gtk.IWidget) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if _, exists := s.updates[name]; !exists {
		return fmt.Errorf("module '%s' is not scheduled", name)
	}

	s.widgetMap[name] = widget

	if info, ok := s.updates[name]; ok {
		info.Widget = widget
	}

	return nil
}

// TriggerManualUpdate triggers a manual update for a module (for ON_DEMAND modules)
func (s *UpdateScheduler) TriggerManualUpdate(name string) error {
	s.mu.RLock()
	info, exists := s.updates[name]
	s.mu.RUnlock()

	if !exists {
		return fmt.Errorf("module '%s' is not scheduled", name)
	}

	if info.Module.UpdateMode() != UpdateModeOnDemand {
		return fmt.Errorf("module '%s' is not ON_DEMAND", name)
	}

	return s.updateModule(name)
}

// HandleIPCMessage handles an IPC message and routes it to the appropriate module
func (s *UpdateScheduler) HandleIPCMessage(message string) bool {
	var handledModule string

	s.mu.RLock()
	log.Printf("[SCHEDULER] Checking modules in updates map: %d modules", len(s.updates))
	for name := range s.updates {
		log.Printf("[SCHEDULER] Checking module '%s' for IPC handling", name)
		if handled := s.registry.HandleModuleIPC(name, message); handled {
			handledModule = name
			break
		}
	}
	s.mu.RUnlock()

	// Trigger widget update for ON_DEMAND modules outside of lock
	if handledModule != "" {
		log.Printf("[SCHEDULER] IPC message handled by module: %s", handledModule)
		s.mu.RLock()
		info, ok := s.updates[handledModule]
		s.mu.RUnlock()

		if ok && info.Module.UpdateMode() == UpdateModeOnDemand {
			_ = s.updateModule(handledModule)
		}
		return true
	}

	log.Printf("[SCHEDULER] IPC message not handled by any module: %s", message)
	return false
}

// HandleClick handles a click event for a module
func (s *UpdateScheduler) HandleClick(name string) bool {
	s.mu.RLock()
	widget, exists := s.widgetMap[name]
	s.mu.RUnlock()

	if !exists {
		return false
	}

	return s.registry.HandleModuleClick(name, widget)
}

// run runs the scheduler's main loop
func (s *UpdateScheduler) run() {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("Recovered from panic in scheduler run loop: %v", r)
		}
	}()

	for {
		select {
		case <-s.ctx.Done():
			return
		case <-s.periodicTicker.C:
			s.UpdateModulesByMode(UpdateModePeriodic)
		}
	}
}

// cleanupAllUpdates cleans up all scheduled updates
func (s *UpdateScheduler) cleanupAllUpdates() {
	for name := range s.updates {
		s.UnscheduleModule(name)
	}
}

// IsRunning returns whether the scheduler is running
func (s *UpdateScheduler) IsRunning() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return s.running
}
