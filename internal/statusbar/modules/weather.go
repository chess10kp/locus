package modules

import (
	"fmt"
	"os/exec"
	"strings"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// WeatherModule displays current weather
type WeatherModule struct {
	*statusbar.BaseModule
	widget      *gtk.Label
	service     string
	location    string
	format      string
	showIcon    bool
	showDetails bool
	command     string
	condition   string
	temperature string
	icon        string
}

// NewWeatherModule creates a new weather module
func NewWeatherModule() *WeatherModule {
	return &WeatherModule{
		BaseModule:  statusbar.NewBaseModule("weather", statusbar.UpdateModePeriodic),
		widget:      nil,
		service:     "wttr.in",
		location:    "",
		format:      "%c+%t+%C",
		showIcon:    true,
		showDetails: true,
		command:     "",
		condition:   "",
		temperature: "",
		icon:        "",
	}
}

// CreateWidget creates a weather label widget
func (m *WeatherModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.formatWeather())
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

// UpdateWidget updates weather widget
func (m *WeatherModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	m.readWeather()
	formatted := m.formatWeather()
	label.SetText(formatted)

	return nil
}

// Initialize initializes the module with configuration
func (m *WeatherModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if service, ok := config["service"].(string); ok {
		m.service = service
	}

	if location, ok := config["location"].(string); ok {
		m.location = location
	}

	if format, ok := config["format"].(string); ok {
		m.format = format
	}

	if showIcon, ok := config["show_icon"].(bool); ok {
		m.showIcon = showIcon
	}

	if showDetails, ok := config["show_details"].(bool); ok {
		m.showDetails = showDetails
	}

	// Build command
	url := fmt.Sprintf("%s/%s?format=%s", m.service, m.location, m.format)
	m.command = fmt.Sprintf("curl -s \"%s\"", url)

	m.SetCSSClasses([]string{"weather-module"})

	m.readWeather()

	return nil
}

// readWeather reads weather from service
func (m *WeatherModule) readWeather() {
	cmd := exec.Command("sh", "-c", m.command)
	output, err := cmd.Output()
	if err != nil {
		m.condition = ""
		m.temperature = ""
		m.icon = ""
		return
	}

	data := strings.TrimSpace(string(output))
	if data == "" {
		m.condition = ""
		m.temperature = ""
		m.icon = ""
		return
	}

	// Parse wttr.in format: icon+temp+condition
	parts := strings.Split(data, "+")
	if len(parts) >= 3 {
		m.icon = strings.TrimSpace(parts[0])
		m.temperature = strings.TrimSpace(parts[1])
		m.condition = strings.TrimSpace(parts[2])
	} else {
		// Fallback: assume whole string is condition + temp
		m.condition = data
		m.temperature = ""
		m.icon = ""
	}
}

// formatWeather formats weather for display
func (m *WeatherModule) formatWeather() string {
	if m.condition == "" && m.temperature == "" {
		return ""
	}

	var builder strings.Builder

	if m.showIcon && m.icon != "" {
		// Map wttr.in icons to emojis if possible
		emojiIcon := m.mapIconToEmoji(m.icon)
		if emojiIcon != "" {
			builder.WriteString(emojiIcon)
			builder.WriteString(" ")
		}
	}

	if m.temperature != "" {
		builder.WriteString(m.temperature)
	}

	if m.showDetails && m.condition != "" {
		if m.temperature != "" {
			builder.WriteString(" ")
		}
		builder.WriteString(m.condition)
	}

	return builder.String()
}

// mapIconToEmoji maps wttr.in icons to emojis
func (m *WeatherModule) mapIconToEmoji(icon string) string {
	// Common wttr.in icons to emojis
	switch icon {
	case "☀️":
		return "☀️"
	case "🌤️":
		return "⛅"
	case "⛅":
		return "⛅"
	case "☁️":
		return "☁️"
	case "🌧️":
		return "🌧️"
	case "⛈️":
		return "⛈️"
	case "🌨️":
		return "🌨️"
	case "❄️":
		return "❄️"
	case "🌫️":
		return "🌫️"
	default:
		return icon // Use as-is if already emoji
	}
}

// GetCondition returns current weather condition
func (m *WeatherModule) GetCondition() string {
	return m.condition
}

// GetTemperature returns current temperature
func (m *WeatherModule) GetTemperature() string {
	return m.temperature
}

// GetIcon returns current weather icon
func (m *WeatherModule) GetIcon() string {
	return m.icon
}

// Cleanup cleans up resources
func (m *WeatherModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// WeatherModuleFactory is a factory for creating WeatherModule instances
type WeatherModuleFactory struct{}

// CreateModule creates a new WeatherModule instance
func (f *WeatherModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewWeatherModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *WeatherModuleFactory) ModuleName() string {
	return "weather"
}

// DefaultConfig returns default configuration
func (f *WeatherModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"service":      "wttr.in",
		"location":     "",
		"format":       "%c+%t+%C",
		"show_icon":    true,
		"show_details": true,
		"interval":     "900s", // 15 minutes
		"css_classes":  []string{"weather-module"},
	}
}

// Dependencies returns module dependencies
func (f *WeatherModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &WeatherModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
