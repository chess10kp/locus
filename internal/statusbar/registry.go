package statusbar

import (
	"fmt"
	"log"

	"github.com/sigma/locus-go/internal/config"
)

type LauncherCallback interface {
	PresentLauncher() error
	HideLauncher() error
}

// ModuleManager manages all status bar modules
type ModuleManager struct {
	modules          map[string]Module
	launcherCallback LauncherCallback
	config           *config.Config
}

// NewModuleManager creates a new module manager
func NewModuleManager(callback LauncherCallback, cfg *config.Config) *ModuleManager {
	return &ModuleManager{
		modules:          make(map[string]Module),
		launcherCallback: callback,
		config:           cfg,
	}
}

// RegisterModule registers a module
func (m *ModuleManager) RegisterModule(module Module) error {
	name := module.Name()

	if _, exists := m.modules[name]; exists {
		return fmt.Errorf("module '%s' already registered", name)
	}

	m.modules[name] = module
	log.Printf("Registered module: %s", name)

	return nil
}

// UnregisterModule unregisters a module
func (m *ModuleManager) UnregisterModule(name string) {
	if module, exists := m.modules[name]; exists {
		module.Cleanup()
		delete(m.modules, name)
		log.Printf("Unregistered module: %s", name)
	}
}

// GetModule returns a module by name
func (m *ModuleManager) GetModule(name string) (Module, bool) {
	module, exists := m.modules[name]
	return module, exists
}

// CreateModule creates a module instance by name
func (m *ModuleManager) CreateModule(name string) (Module, error) {
	switch name {
	case "launcher":
		return NewLauncherModule(m.launcherCallback), nil
	case "time":
		return NewTimeModule(m.config), nil
	case "battery":
		return NewBatteryModule(), nil
	case "workspaces":
		return NewWorkspacesModule(), nil
	case "binding_mode":
		return NewBindingModeModule(), nil
	case "emacs_clock":
		return NewEmacsClockModule(m.config), nil
	case "custom_message":
		return NewCustomMessageModule(), nil
	case "notifications":
		return NewNotificationModule(m.config), nil
	default:
		return nil, fmt.Errorf("unknown module: %s", name)
	}
}

// LoadModules loads all configured modules
func (m *ModuleManager) LoadModules(moduleNames []string) error {
	for _, name := range moduleNames {
		module, err := m.CreateModule(name)
		if err != nil {
			log.Printf("Failed to create module '%s': %v", name, err)
			continue
		}

		if module != nil {
			m.modules[name] = module
			log.Printf("Loaded module: %s", name)
		}
	}

	return nil
}

// UpdateAll updates all modules that need updates
func (m *ModuleManager) UpdateAll() {
	for name, module := range m.modules {
		mode := module.UpdateMode()

		if mode == UpdateModeStatic || mode == UpdateModeOnDemand {
			continue
		}

		widget := module.CreateWidget()
		if widget == nil {
			continue
		}

		module.Update(widget)

		log.Printf("Updated module: %s", name)
	}
}

// Cleanup cleans up all modules
func (m *ModuleManager) Cleanup() {
	for name, module := range m.modules {
		module.Cleanup()
		log.Printf("Cleaned up module: %s", name)
	}

	m.modules = make(map[string]Module)
}

// HandleIPCMessage routes IPC messages to appropriate modules
func (m *ModuleManager) HandleIPCMessage(message string) bool {
	for _, module := range m.modules {
		if module.HandlesIPC() {
			if module.HandleIPC(message) {
				log.Printf("Module '%s' handled IPC: %s", module.Name(), message)
				return true
			}
		}
	}

	return false
}

// GetWidgets returns widgets for all modules
func (m *ModuleManager) GetWidgets() map[string]*Widget {
	widgets := make(map[string]*Widget)
	for name, module := range m.modules {
		widgets[name] = module.CreateWidget()
	}
	return widgets
}

// GetModules returns all registered modules
func (m *ModuleManager) GetModules() map[string]Module {
	return m.modules
}
