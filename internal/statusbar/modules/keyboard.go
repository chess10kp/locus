package modules

import (
	"os/exec"
	"strconv"
	"strings"

	"github.com/gotk3/gotk3/gtk"
	"github.com/chess10kp/locus/internal/statusbar"
)

// KeyboardModule displays keyboard layout and lock states
type KeyboardModule struct {
	*statusbar.BaseModule
	widget     *gtk.Label
	layoutCmd  string
	locksCmd   string
	showIcon   bool
	showLayout bool
	showLocks  bool
	layout     string
	capsLock   bool
	numLock    bool
}

// NewKeyboardModule creates a new keyboard module
func NewKeyboardModule() *KeyboardModule {
	return &KeyboardModule{
		BaseModule: statusbar.NewBaseModule("keyboard", statusbar.UpdateModePeriodic),
		widget:     nil,
		layoutCmd:  "setxkbmap -query | grep layout | awk '{print toupper($2)}'",
		locksCmd:   "xset q | grep LED | awk '{print $10}'",
		showIcon:   true,
		showLayout: true,
		showLocks:  true,
		layout:     "",
		capsLock:   false,
		numLock:    false,
	}
}

// CreateWidget creates a keyboard label widget
func (m *KeyboardModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.formatKeyboard())
	if err != nil {
		return nil, err
	}

	m.widget = label

	helper := &statusbar.WidgetHelper{}
	if err := helper.ApplyStylesToWidget(label, m.GetStyles(), m.GetCSSClasses()); err != nil {
		return nil, err
	}

	return label, nil
}

// UpdateWidget updates keyboard widget
func (m *KeyboardModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	m.readKeyboardStatus()
	formatted := m.formatKeyboard()
	label.SetText(formatted)

	// Update CSS classes for color
	if ctx, err := label.ToWidget().GetStyleContext(); err == nil {
		ctx.RemoveClass("keyboard-caps")
		ctx.RemoveClass("keyboard-num")
		if m.capsLock {
			ctx.AddClass("keyboard-caps")
		}
		if m.numLock {
			ctx.AddClass("keyboard-num")
		}
	}

	return nil
}

// Initialize initializes the module with configuration
func (m *KeyboardModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if layoutCmd, ok := config["layout_cmd"].(string); ok {
		m.layoutCmd = layoutCmd
	}

	if locksCmd, ok := config["locks_cmd"].(string); ok {
		m.locksCmd = locksCmd
	}

	if showIcon, ok := config["show_icon"].(bool); ok {
		m.showIcon = showIcon
	}

	if showLayout, ok := config["show_layout"].(bool); ok {
		m.showLayout = showLayout
	}

	if showLocks, ok := config["show_locks"].(bool); ok {
		m.showLocks = showLocks
	}

	m.SetCSSClasses([]string{"keyboard-module"})

	m.readKeyboardStatus()

	return nil
}

// readKeyboardStatus reads keyboard status from system
func (m *KeyboardModule) readKeyboardStatus() {
	// Get layout
	if cmd := exec.Command("sh", "-c", m.layoutCmd); cmd != nil {
		if output, err := cmd.Output(); err == nil {
			m.layout = strings.TrimSpace(string(output))
		}
	}

	// Get lock states
	if cmd := exec.Command("sh", "-c", m.locksCmd); cmd != nil {
		if output, err := cmd.Output(); err == nil {
			if maskStr := strings.TrimSpace(string(output)); maskStr != "" {
				if mask, err := strconv.Atoi(maskStr); err == nil {
					m.capsLock = (mask & 1) != 0 // CAPS lock is bit 0
					m.numLock = (mask & 2) != 0  // NUM lock is bit 1
				}
			}
		}
	}
}

// formatKeyboard formats keyboard status for display
func (m *KeyboardModule) formatKeyboard() string {
	var builder strings.Builder

	if m.showIcon {
		builder.WriteString("⌨️ ")
	}

	if m.showLayout && m.layout != "" {
		builder.WriteString(m.layout)
	}

	if m.showLocks {
		var locks []string
		if m.capsLock {
			locks = append(locks, "CAPS 🔒")
		}
		if m.numLock {
			locks = append(locks, "NUM 🔢")
		}

		if len(locks) > 0 {
			if m.showLayout && m.layout != "" {
				builder.WriteString(" ")
			}
			builder.WriteString(strings.Join(locks, " "))
		}
	}

	// If nothing to show, return empty
	if builder.Len() == 0 || (builder.String() == "⌨️ " && !m.showLayout && !m.showLocks) {
		return ""
	}

	return builder.String()
}

// GetLayout returns current keyboard layout
func (m *KeyboardModule) GetLayout() string {
	return m.layout
}

// IsCapsLock returns CAPS lock state
func (m *KeyboardModule) IsCapsLock() bool {
	return m.capsLock
}

// IsNumLock returns NUM lock state
func (m *KeyboardModule) IsNumLock() bool {
	return m.numLock
}

// Cleanup cleans up resources
func (m *KeyboardModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// KeyboardModuleFactory is a factory for creating KeyboardModule instances
type KeyboardModuleFactory struct{}

// CreateModule creates a new KeyboardModule instance
func (f *KeyboardModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewKeyboardModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *KeyboardModuleFactory) ModuleName() string {
	return "keyboard"
}

// DefaultConfig returns default configuration
func (f *KeyboardModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"layout_cmd":  "setxkbmap -query | grep layout | awk '{print toupper($2)}'",
		"locks_cmd":   "xset q | grep LED | awk '{print $10}'",
		"show_icon":   true,
		"show_layout": true,
		"show_locks":  true,
		"interval":    "5s",
		"css_classes": []string{"keyboard-module"},
	}
}

// Dependencies returns module dependencies
func (f *KeyboardModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &KeyboardModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
