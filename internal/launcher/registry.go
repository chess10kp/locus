package launcher

import (
	"fmt"
	"log"
	"strings"

	"github.com/sigma/locus-go/internal/core"
)

// LauncherSizeMode represents launcher window size mode
type LauncherSizeMode int

const (
	LauncherSizeModeDefault LauncherSizeMode = iota
	LauncherSizeModeWallpaper
	LauncherSizeModeGrid
	LauncherSizeModeCustom
)

// Launcher is the interface that all launchers must implement
type Launcher interface {
	Name() string
	CommandTriggers() []string
	GetSizeMode() (LauncherSizeMode, interface{})
	Populate(query string, launcherCore *core.Launcher)
	HandlesEnter() bool
	HandleEnter(query string, launcherCore *core.Launcher) bool
	HandlesTab() bool
	HandleTab(query string) string
	Cleanup()
}

// LauncherRegistry manages all launchers
type LauncherRegistry struct {
	launchers    map[string]Launcher
	triggerMap   map[string]Launcher
	customPrefix map[string]string // name -> custom prefix
}

// NewLauncherRegistry creates a new launcher registry
func NewLauncherRegistry() *LauncherRegistry {
	return &LauncherRegistry{
		launchers:    make(map[string]Launcher),
		triggerMap:   make(map[string]Launcher),
		customPrefix: make(map[string]string),
	}
}

// Register registers a launcher
func (r *LauncherRegistry) Register(launcher Launcher) error {
	name := launcher.Name()

	if _, exists := r.launchers[name]; exists {
		return fmt.Errorf("launcher '%s' already registered", name)
	}

	r.launchers[name] = launcher

	// Register triggers
	for _, trigger := range launcher.CommandTriggers() {
		r.triggerMap[trigger] = launcher
		log.Printf("Registered trigger: %s -> %s", trigger, name)
	}

	return nil
}

// RegisterWithCustomPrefix registers a launcher with custom prefix
func (r *LauncherRegistry) RegisterWithCustomPrefix(launcher Launcher, prefix string) error {
	name := launcher.Name()

	if err := r.Register(launcher); err != nil {
		return err
	}

	r.customPrefix[name] = prefix
	r.triggerMap[prefix] = launcher

	log.Printf("Registered custom prefix: %s -> %s", prefix, name)

	return nil
}

// Unregister unregisters a launcher
func (r *LauncherRegistry) Unregister(name string) {
	if launcher, exists := r.launchers[name]; exists {
		// Remove triggers
		for _, trigger := range launcher.CommandTriggers() {
			delete(r.triggerMap, trigger)
		}

		// Remove custom prefix
		if prefix, ok := r.customPrefix[name]; ok {
			delete(r.triggerMap, prefix)
			delete(r.customPrefix, name)
		}

		launcher.Cleanup()
		delete(r.launchers, name)

		log.Printf("Unregistered launcher: %s", name)
	}
}

// GetLauncher returns a launcher by trigger
func (r *LauncherRegistry) GetLauncher(trigger string) (Launcher, bool) {
	launcher, exists := r.triggerMap[trigger]
	return launcher, exists
}

// FindLauncherForInput finds a launcher for given input
func (r *LauncherRegistry) FindLauncherForInput(input string) (trigger string, launcher Launcher, query string) {
	// Check for > prefix
	if strings.HasPrefix(input, ">") {
		parts := strings.SplitN(input[1:], " ", 2)
		if len(parts) > 0 {
			trigger = parts[0]
			if len(parts) > 1 {
				query = parts[1]
			}

			launcher, exists := r.GetLauncher(trigger)
			if exists {
				return trigger, launcher, query
			}
		}
	}

	// Check for colon-style triggers (f:, wp:, etc.)
	if strings.Contains(input, ":") {
		parts := strings.SplitN(input, ":", 2)
		if len(parts) > 1 {
			trigger = parts[0]
			query = strings.TrimSpace(parts[1])

			launcher, exists := r.GetLauncher(trigger)
			if exists {
				return trigger, launcher, query
			}
		}
	}

	// Check for space-style triggers (f , m , etc.)
	if strings.Contains(input, " ") {
		parts := strings.SplitN(input, " ", 2)
		if len(parts) > 1 {
			trigger = parts[0]
			query = strings.TrimSpace(parts[1])

			launcher, exists := r.GetLauncher(trigger)
			if exists {
				return trigger, launcher, query
			}
		}
	}

	return "", nil, ""
}

// GetAllLaunchers returns all registered launchers
func (r *LauncherRegistry) GetAllLaunchers() []Launcher {
	launchers := make([]Launcher, 0, len(r.launchers))
	for _, launcher := range r.launchers {
		launchers = append(launchers, launcher)
	}
	return launchers
}

// Cleanup cleans up all launchers
func (r *LauncherRegistry) Cleanup() {
	for name, launcher := range r.launchers {
		launcher.Cleanup()
		log.Printf("Cleaned up launcher: %s", name)
	}

	r.launchers = make(map[string]Launcher)
	r.triggerMap = make(map[string]Launcher)
	r.customPrefix = make(map[string]string)
}
