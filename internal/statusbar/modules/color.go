package modules

import (
	"fmt"
	"log"

	"github.com/chess10kp/locus/internal/statusbar"
	"github.com/gotk3/gotk3/gdk"
	"github.com/gotk3/gotk3/gtk"
)

// ColorModule displays the last selected color
type ColorModule struct {
	*statusbar.BaseModule
	widget   *gtk.EventBox
	colorBox *gtk.Box
	color    string
	tooltip  string
}

// NewColorModule creates a new color module
func NewColorModule() *ColorModule {
	return &ColorModule{
		BaseModule: statusbar.NewBaseModule("color", statusbar.UpdateModeOnDemand),
		widget:     nil,
		colorBox:   nil,
		color:      "#888888",
		tooltip:    "No color selected",
	}
}

// CreateWidget creates a color display widget
func (m *ColorModule) CreateWidget() (gtk.IWidget, error) {
	eventBox, err := gtk.EventBoxNew()
	if err != nil {
		return nil, err
	}

	colorBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 4)
	if err != nil {
		return nil, err
	}

	// Create color indicator box with direct background color
	indicator, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 0)
	if err != nil {
		return nil, err
	}
	indicator.SetSizeRequest(16, 16)

	// Set initial background color directly on indicator
	m.updateIndicatorColor(indicator)

	label, err := gtk.LabelNew(m.color)
	if err != nil {
		return nil, err
	}
	label.SetMarginStart(4)
	label.SetMarginEnd(4)

	colorBox.PackStart(indicator, false, false, 2)
	colorBox.PackStart(label, false, false, 2)
	eventBox.Add(colorBox)

	m.widget = eventBox
	m.colorBox = colorBox

	// Set up click handler
	m.widget.Connect("button-press-event", func() {
		log.Printf("Color module clicked")
		if m.HandlesClicks() {
			m.HandleClick(m.widget)
		}
	})

	// Apply initial color
	m.updateWidget()

	helper := &statusbar.WidgetHelper{}
	if err := helper.ApplyStylesToWidget(eventBox, m.GetStyles(), m.GetCSSClasses()); err != nil {
		return nil, err
	}

	return eventBox, nil
}

// UpdateWidget updates the color display
func (m *ColorModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	return m.updateWidget()
}

// updateWidget applies the current color to the widget
func (m *ColorModule) updateWidget() error {
	if m.colorBox == nil {
		return nil
	}

	// Update CSS for color indicator
	css := `
		#color-indicator {
			background-color: ` + m.color + `;
			border-radius: 3px;
			border: 1px solid rgba(255, 255, 255, 0.3);
		}
	`

	// Apply inline style to color box
	styleProvider, err := gtk.CssProviderNew()
	if err != nil {
		return err
	}

	if err := styleProvider.LoadFromData(css); err != nil {
		return err
	}

	screen, err := gdk.ScreenGetDefault()
	if err != nil {
		return err
	}

	gtk.AddProviderForScreen(screen, styleProvider, gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

	// Update label
	children := m.colorBox.GetChildren()
	if children.Length() > 1 {
		if label, ok := children.NthData(1).(*gtk.Label); ok {
			label.SetText(m.color)
		}
	}

	// Update tooltip
	if m.widget != nil {
		m.widget.SetTooltipText(m.tooltip)
	}

	return nil
}

// updateIndicatorColor updates the color indicator's background
func (m *ColorModule) updateIndicatorColor(indicator *gtk.Box) {
	// Apply background color directly to the widget using a unique ID
	indicator.SetName(fmt.Sprintf("color-indicator-%s", m.color))

	// Create CSS with ID selector (not class selector)
	css := fmt.Sprintf(`
		#color-indicator-%s {
			background-color: %s;
			border-radius: 3px;
			min-width: 16px;
			min-height: 16px;
			border: 1px solid rgba(255,255,255,0.3);
		}
	`, m.color, m.color)

	// Get or create style provider
	styleProvider, err := gtk.CssProviderNew()
	if err != nil {
		log.Printf("Failed to create CSS provider: %v", err)
		return
	}

	if err := styleProvider.LoadFromData(css); err != nil {
		log.Printf("Failed to load CSS: %v", err)
		return
	}

	screen, err := gdk.ScreenGetDefault()
	if err != nil {
		log.Printf("Failed to get screen: %v", err)
		return
	}

	gtk.AddProviderForScreen(screen, styleProvider, gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
}

// SetColor sets the current color
func (m *ColorModule) SetColor(color string) {
	m.color = color
	m.tooltip = color

	// Update widget
	if m.widget != nil {
		m.updateWidget()
	}
}

// GetColor returns the current color
func (m *ColorModule) GetColor() string {
	return m.color
}

// Initialize initializes the module with configuration
func (m *ColorModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if color, ok := config["color"].(string); ok {
		m.color = color
		m.tooltip = color
	}

	m.SetCSSClasses([]string{"color-module"})

	m.SetClickHandler(func(widget gtk.IWidget) bool {
		log.Printf("Color module clicked, copying to clipboard: %s", m.color)
		// TODO: Implement clipboard copy via IPC
		return true
	})

	m.SetIPCHandler(func(message string) bool {
		log.Printf("ColorModule received IPC: %s", message)

		// Handle color update messages
		if len(message) > 6 && message[:6] == "color:" {
			color := message[6:]
			m.SetColor(color)
			return true
		}

		return false
	})

	return nil
}

// Cleanup cleans up resources
func (m *ColorModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// ColorModuleFactory is a factory for creating ColorModule instances
type ColorModuleFactory struct{}

// CreateModule creates a new ColorModule instance
func (f *ColorModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewColorModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns the module name
func (f *ColorModuleFactory) ModuleName() string {
	return "color"
}

// DefaultConfig returns the default configuration
func (f *ColorModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"color":       "#888888",
		"css_classes": []string{"color-module"},
	}
}

// Dependencies returns the module dependencies
func (f *ColorModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &ColorModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
