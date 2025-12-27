package statusbar

import (
	"fmt"
	"log"
	"sync"

	"github.com/gotk3/gotk3/glib"
	"github.com/gotk3/gotk3/gtk"
)

// ModuleFactory is the interface that module factories must implement
type ModuleFactory interface {
	// CreateModule creates a new module instance with the given configuration
	CreateModule(config map[string]interface{}) (Module, error)

	// ModuleName returns the name of modules this factory creates
	ModuleName() string

	// DefaultConfig returns the default configuration for the module
	DefaultConfig() map[string]interface{}

	// Dependencies returns the list of dependencies required by this module
	Dependencies() []string
}

// ModuleRegistry manages module factories and instances
type ModuleRegistry struct {
	factories    map[string]ModuleFactory
	modules      map[string]Module
	listeners    map[string][]EventListener
	mu           sync.RWMutex
	widgetHelper *WidgetHelper
	initialized  bool
}

// NewModuleRegistry creates a new module registry
func NewModuleRegistry() *ModuleRegistry {
	return &ModuleRegistry{
		factories:    make(map[string]ModuleFactory),
		modules:      make(map[string]Module),
		listeners:    make(map[string][]EventListener),
		widgetHelper: &WidgetHelper{},
		initialized:  false,
	}
}

// RegisterFactory registers a module factory
func (r *ModuleRegistry) RegisterFactory(factory ModuleFactory) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	name := factory.ModuleName()

	if _, exists := r.factories[name]; exists {
		return fmt.Errorf("factory for module '%s' already registered", name)
	}

	r.factories[name] = factory
	log.Printf("Registered module factory: %s", name)

	return nil
}

// UnregisterFactory unregisters a module factory
func (r *ModuleRegistry) UnregisterFactory(name string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.factories[name]; !exists {
		return fmt.Errorf("factory for module '%s' not found", name)
	}

	delete(r.factories, name)
	log.Printf("Unregistered module factory: %s", name)

	return nil
}

// CreateModule creates a module instance by name with the given configuration
func (r *ModuleRegistry) CreateModule(name string, config map[string]interface{}) (Module, error) {
	r.mu.RLock()
	factory, exists := r.factories[name]
	r.mu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("no factory registered for module '%s'", name)
	}

	module, err := factory.CreateModule(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create module '%s': %w", name, err)
	}

	return module, nil
}

// CreateModuleWithDefaults creates a module instance with default configuration
func (r *ModuleRegistry) CreateModuleWithDefaults(name string) (Module, error) {
	r.mu.RLock()
	factory, exists := r.factories[name]
	r.mu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("no factory registered for module '%s'", name)
	}

	config := factory.DefaultConfig()
	return r.CreateModule(name, config)
}

// RegisterModule registers a module instance directly
func (r *ModuleRegistry) RegisterModule(module Module) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	name := module.Name()

	if _, exists := r.modules[name]; exists {
		return fmt.Errorf("module '%s' already registered", name)
	}

	if !module.IsInitialized() {
		defaultConfig := r.getDefaultConfig(name)
		if err := module.Initialize(defaultConfig); err != nil {
			return fmt.Errorf("failed to initialize module '%s': %w", name, err)
		}
	}

	r.modules[name] = module
	log.Printf("Registered module instance: %s", name)

	return nil
}

// UnregisterModule unregisters a module instance
func (r *ModuleRegistry) UnregisterModule(name string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	module, exists := r.modules[name]
	if !exists {
		return fmt.Errorf("module '%s' not found", name)
	}

	module.Cleanup()
	delete(r.modules, name)

	if listeners, ok := r.listeners[name]; ok {
		for _, listener := range listeners {
			listener.Cleanup()
		}
		delete(r.listeners, name)
	}

	log.Printf("Unregistered module instance: %s", name)

	return nil
}

// GetModule returns a module instance by name
func (r *ModuleRegistry) GetModule(name string) (Module, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	module, exists := r.modules[name]
	return module, exists
}

// ListModules returns all registered module names
func (r *ModuleRegistry) ListModules() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()

	names := make([]string, 0, len(r.modules))
	for name := range r.modules {
		names = append(names, name)
	}

	return names
}

// ListFactories returns all registered factory names
func (r *ModuleRegistry) ListFactories() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()

	names := make([]string, 0, len(r.factories))
	for name := range r.factories {
		names = append(names, name)
	}

	return names
}

// GetModulesByUpdateMode returns all modules with a specific update mode
func (r *ModuleRegistry) GetModulesByUpdateMode(mode UpdateMode) []Module {
	r.mu.RLock()
	defer r.mu.RUnlock()

	modules := make([]Module, 0)
	for _, module := range r.modules {
		if module.UpdateMode() == mode {
			modules = append(modules, module)
		}
	}

	return modules
}

// CreateAndRegisterModule creates and registers a module in one step
func (r *ModuleRegistry) CreateAndRegisterModule(name string, config map[string]interface{}) (Module, error) {
	module, err := r.CreateModule(name, config)
	if err != nil {
		return nil, err
	}

	if err := r.RegisterModule(module); err != nil {
		return nil, err
	}

	return module, nil
}

// CreateAndRegisterModuleWithDefaults creates and registers a module with default config
func (r *ModuleRegistry) CreateAndRegisterModuleWithDefaults(name string) (Module, error) {
	module, err := r.CreateModuleWithDefaults(name)
	if err != nil {
		return nil, err
	}

	if err := r.RegisterModule(module); err != nil {
		return nil, err
	}

	return module, nil
}

// SetupModuleEventListeners sets up event listeners for a module
func (r *ModuleRegistry) SetupModuleEventListeners(name string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	module, exists := r.modules[name]
	if !exists {
		return fmt.Errorf("module '%s' not found", name)
	}

	listeners, err := module.SetupEventListeners()
	if err != nil {
		return fmt.Errorf("failed to setup event listeners for module '%s': %w", name, err)
	}

	if listeners != nil && len(listeners) > 0 {
		r.listeners[name] = listeners
		log.Printf("Set up %d event listeners for module '%s'", len(listeners), name)
	}

	return nil
}

// StartModuleListeners starts event listeners for a module
func (r *ModuleRegistry) StartModuleListeners(name string, callback func()) error {
	r.mu.RLock()
	listeners, exists := r.listeners[name]
	_, moduleExists := r.modules[name]
	r.mu.RUnlock()

	if !exists {
		return fmt.Errorf("no listeners registered for module '%s'", name)
	}

	if !moduleExists {
		return fmt.Errorf("module '%s' not found", name)
	}

	for _, listener := range listeners {
		if err := listener.Start(callback); err != nil {
			return fmt.Errorf("failed to start listener for module '%s': %w", name, err)
		}
	}

	log.Printf("Started event listeners for module '%s'", name)

	return nil
}

// StopModuleListeners stops event listeners for a module
func (r *ModuleRegistry) StopModuleListeners(name string) error {
	r.mu.RLock()
	listeners, exists := r.listeners[name]
	r.mu.RUnlock()

	if !exists {
		return fmt.Errorf("no listeners registered for module '%s'", name)
	}

	for _, listener := range listeners {
		if err := listener.Stop(); err != nil {
			log.Printf("Failed to stop listener for module '%s': %v", name, err)
		}
	}

	log.Printf("Stopped event listeners for module '%s'", name)

	return nil
}

// CreateWidgetForModule creates a GTK widget for a module
func (r *ModuleRegistry) CreateWidgetForModule(name string) (gtk.IWidget, error) {
	r.mu.RLock()
	module, exists := r.modules[name]
	r.mu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("module '%s' not found", name)
	}

	widget, err := module.CreateWidget()
	if err != nil {
		return nil, fmt.Errorf("failed to create widget for module '%s': %w", name, err)
	}

	styles := module.GetStyles()
	classes := module.GetCSSClasses()

	if styles != "" || len(classes) > 0 {
		if err := r.widgetHelper.ApplyStylesToWidget(widget, styles, classes); err != nil {
			log.Printf("Warning: failed to apply styles to module '%s': %v", name, err)
		}
	}

	return widget, nil
}

// UpdateModuleWidget updates a module's widget
func (r *ModuleRegistry) UpdateModuleWidget(name string, widget gtk.IWidget) error {
	r.mu.RLock()
	module, exists := r.modules[name]
	r.mu.RUnlock()

	if !exists {
		return fmt.Errorf("module '%s' not found", name)
	}

	// GTK operations must be performed on the main thread
	// Use a channel to synchronously wait for the result
	errChan := make(chan error, 1)

	glib.IdleAdd(func() {
		err := module.UpdateWidget(widget)
		errChan <- err
	})

	return <-errChan
}

// HandleModuleClick handles a click event for a module
func (r *ModuleRegistry) HandleModuleClick(name string, widget gtk.IWidget) bool {
	r.mu.RLock()
	module, exists := r.modules[name]
	r.mu.RUnlock()

	if !exists {
		return false
	}

	return module.HandleClick(widget)
}

// HandleModuleIPC handles an IPC message for a module
func (r *ModuleRegistry) HandleModuleIPC(name string, message string) bool {
	r.mu.RLock()
	module, exists := r.modules[name]
	r.mu.RUnlock()

	if !exists {
		log.Printf("[REGISTRY] Module '%s' does not exist, cannot handle IPC", name)
		return false
	}

	handled := module.HandleIPC(message)
	log.Printf("[REGISTRY] IPC message to module '%s': handled=%v, message=%s", name, handled, message)
	return handled
}

// CleanupAll cleans up all modules and listeners
func (r *ModuleRegistry) CleanupAll() {
	r.mu.Lock()
	defer r.mu.Unlock()

	for name := range r.listeners {
		if listeners, ok := r.listeners[name]; ok {
			for _, listener := range listeners {
				listener.Cleanup()
			}
		}
		delete(r.listeners, name)
	}

	for name := range r.modules {
		if module, ok := r.modules[name]; ok {
			module.Cleanup()
		}
		delete(r.modules, name)
	}

	log.Printf("Cleaned up all modules and listeners")
}

// getDefaultConfig gets the default configuration for a module
func (r *ModuleRegistry) getDefaultConfig(name string) map[string]interface{} {
	r.mu.RLock()
	factory, exists := r.factories[name]
	r.mu.RUnlock()

	if !exists {
		return make(map[string]interface{})
	}

	return factory.DefaultConfig()
}

// GetWidgetHelper returns the widget helper
func (r *ModuleRegistry) GetWidgetHelper() *WidgetHelper {
	return r.widgetHelper
}

// Global registry instance
var defaultRegistry *ModuleRegistry
var registryOnce sync.Once

// DefaultRegistry returns the default global module registry
func DefaultRegistry() *ModuleRegistry {
	registryOnce.Do(func() {
		defaultRegistry = NewModuleRegistry()
	})
	return defaultRegistry
}
