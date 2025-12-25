package launcher

import (
	"fmt"
	"log"
	"os/exec"
	"strings"
	"syscall"

	"github.com/sigma/locus-go/internal/config"
)

type LauncherUI interface {
	UpdateResults(items []*LauncherItem)
	HandleCommand(command string)
}

type LauncherContext struct {
	Config *config.Config
	UI     LauncherUI
}

// LauncherSizeMode represents launcher window size mode
type LauncherSizeMode int

const (
	LauncherSizeModeDefault LauncherSizeMode = iota
	LauncherSizeModeWallpaper
	LauncherSizeModeGrid
	LauncherSizeModeCustom
)

// LauncherItem represents a single result item
type LauncherItem struct {
	Title    string
	Subtitle string
	Icon     string
	Command  string
	Launcher Launcher
}

// Launcher is the interface that all launchers must implement
type Launcher interface {
	Name() string
	CommandTriggers() []string
	GetSizeMode() LauncherSizeMode
	Populate(query string, ctx *LauncherContext) []*LauncherItem
	HandlesEnter() bool
	HandleEnter(query string, ctx *LauncherContext) bool
	HandlesTab() bool
	HandleTab(query string) string
	Cleanup()
}

// LauncherRegistry manages all launchers
type LauncherRegistry struct {
	launchers    map[string]Launcher
	triggerMap   map[string]Launcher
	customPrefix map[string]string // name -> custom prefix
	config       *config.Config
	ctx          *LauncherContext
}

// NewLauncherRegistry creates a new launcher registry
func NewLauncherRegistry(cfg *config.Config) *LauncherRegistry {
	return &LauncherRegistry{
		launchers:    make(map[string]Launcher),
		triggerMap:   make(map[string]Launcher),
		customPrefix: make(map[string]string),
		config:       cfg,
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

// Search searches for items matching the query
func (r *LauncherRegistry) Search(query string) ([]*LauncherItem, error) {
	_, l, q := r.FindLauncherForInput(query)

	if l != nil {
		return l.Populate(q, r.ctx), nil
	}

	var items []*LauncherItem

	for _, launcher := range r.launchers {
		launcherItems := launcher.Populate(query, r.ctx)
		items = append(items, launcherItems...)
	}

	return items, nil
}

// Execute executes a launcher item
func (r *LauncherRegistry) Execute(item *LauncherItem) error {
	if item.Launcher != nil {
		if item.Launcher.HandlesEnter() {
			if item.Launcher.HandleEnter(item.Command, r.ctx) {
				return nil
			}
		}
	}

	if item.Command != "" {
		parts := strings.Fields(item.Command)
		if len(parts) == 0 {
			return fmt.Errorf("empty command")
		}

		cmd := exec.Command(parts[0], parts[1:]...)
		cmd.SysProcAttr = &syscall.SysProcAttr{
			Setsid: true,
		}

		if err := cmd.Start(); err != nil {
			return fmt.Errorf("failed to start command: %w", err)
		}

		return nil
	}

	return fmt.Errorf("no executable command")
}

// LoadBuiltIn loads built-in launchers
func (r *LauncherRegistry) LoadBuiltIn() error {
	r.ctx = &LauncherContext{
		Config: r.config,
	}

	launchers := []Launcher{
		NewShellLauncher(),
		NewWebLauncher(),
		NewCalcLauncher(),
		NewBrightnessLauncher(r.config),
		NewScreenshotLauncher(r.config),
		NewLockLauncher(r.config),
		NewTimerLauncher(r.config),
		NewKillLauncher(r.config),
		NewWMFocusLauncher(r.config),
		NewWallpaperLauncher(r.config),
		NewClipboardLauncher(r.config),
		NewWifiLauncher(r.config),
		NewFileLauncher(r.config),
	}

	for _, l := range launchers {
		if err := r.Register(l); err != nil {
			log.Printf("Failed to register launcher %s: %v", l.Name(), err)
		}
	}

	return nil
}
