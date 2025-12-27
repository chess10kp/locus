package modules

import (
	"fmt"
	"os/exec"
	"strings"

	"github.com/gotk3/gotk3/gtk"
	"github.com/chess10kp/locus/internal/statusbar"
)

// MusicModule displays MPD music playback status
type MusicModule struct {
	*statusbar.BaseModule
	widget         *gtk.Label
	host           string
	port           int
	showIcon       bool
	showStatus     bool
	maxLength      int
	currentCmd     string
	statusCmd      string
	artist         string
	title          string
	playbackStatus string
	isPlaying      bool
}

// NewMusicModule creates a new music module
func NewMusicModule() *MusicModule {
	return &MusicModule{
		BaseModule:     statusbar.NewBaseModule("music", statusbar.UpdateModePeriodic),
		widget:         nil,
		host:           "localhost",
		port:           6600,
		showIcon:       true,
		showStatus:     true,
		maxLength:      30,
		currentCmd:     "mpc current",
		statusCmd:      "mpc status",
		artist:         "",
		title:          "",
		playbackStatus: "",
		isPlaying:      false,
	}
}

// CreateWidget creates a music label widget
func (m *MusicModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.formatMusic())
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

// UpdateWidget updates music widget
func (m *MusicModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	m.readMusicStatus()
	formatted := m.formatMusic()
	label.SetText(formatted)

	// Update CSS classes for color
	if ctx, err := label.ToWidget().GetStyleContext(); err == nil {
		ctx.RemoveClass("music-playing")
		ctx.RemoveClass("music-paused")
		switch m.playbackStatus {
		case "playing":
			ctx.AddClass("music-playing")
		case "paused":
			ctx.AddClass("music-paused")
		}
	}

	return nil
}

// Initialize initializes the module with configuration
func (m *MusicModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if host, ok := config["host"].(string); ok {
		m.host = host
	}

	if port, ok := config["port"].(int); ok {
		m.port = port
	}

	if showIcon, ok := config["show_icon"].(bool); ok {
		m.showIcon = showIcon
	}

	if showStatus, ok := config["show_status"].(bool); ok {
		m.showStatus = showStatus
	}

	if maxLength, ok := config["max_length"].(int); ok {
		m.maxLength = maxLength
	}

	// Build commands with host/port
	hostPort := fmt.Sprintf("-h %s -p %d", m.host, m.port)
	m.currentCmd = fmt.Sprintf("mpc %s current", hostPort)
	m.statusCmd = fmt.Sprintf("mpc %s status", hostPort)

	m.SetCSSClasses([]string{"music-module"})

	m.readMusicStatus()

	return nil
}

// readMusicStatus reads music status from MPD
func (m *MusicModule) readMusicStatus() {
	// Get current song
	if cmd := exec.Command("sh", "-c", m.currentCmd); cmd != nil {
		if output, err := cmd.Output(); err == nil {
			current := strings.TrimSpace(string(output))
			if current != "" {
				// Parse artist - title
				parts := strings.SplitN(current, " - ", 2)
				if len(parts) >= 2 {
					m.artist = strings.TrimSpace(parts[0])
					m.title = strings.TrimSpace(parts[1])
				} else {
					m.artist = ""
					m.title = current
				}
			} else {
				m.artist = ""
				m.title = ""
			}
		}
	}

	// Get playback status
	if cmd := exec.Command("sh", "-c", m.statusCmd); cmd != nil {
		if output, err := cmd.Output(); err == nil {
			lines := strings.Split(string(output), "\n")
			if len(lines) > 1 {
				statusLine := strings.TrimSpace(lines[1])
				if strings.Contains(statusLine, "[playing]") {
					m.playbackStatus = "playing"
					m.isPlaying = true
				} else if strings.Contains(statusLine, "[paused]") {
					m.playbackStatus = "paused"
					m.isPlaying = false
				} else if strings.Contains(statusLine, "[stopped]") {
					m.playbackStatus = "stopped"
					m.isPlaying = false
				} else {
					m.playbackStatus = ""
					m.isPlaying = false
				}
			}
		}
	}
}

// formatMusic formats music status for display
func (m *MusicModule) formatMusic() string {
	if m.title == "" {
		return ""
	}

	var builder strings.Builder

	if m.showIcon {
		builder.WriteString("♪ ")
	}

	// Build song info
	var songInfo string
	if m.artist != "" {
		songInfo = fmt.Sprintf("%s - %s", m.artist, m.title)
	} else {
		songInfo = m.title
	}

	// Truncate if too long
	if len(songInfo) > m.maxLength {
		songInfo = songInfo[:m.maxLength-3] + "..."
	}

	builder.WriteString(songInfo)

	if m.showStatus {
		statusIcon := m.getStatusIcon()
		if statusIcon != "" {
			builder.WriteString(" ")
			builder.WriteString(statusIcon)
		}
	}

	return builder.String()
}

// getStatusIcon returns playback status icon
func (m *MusicModule) getStatusIcon() string {
	switch m.playbackStatus {
	case "playing":
		return "▶️"
	case "paused":
		return "⏸️"
	case "stopped":
		return "⏹️"
	default:
		return ""
	}
}

// GetArtist returns current artist
func (m *MusicModule) GetArtist() string {
	return m.artist
}

// GetTitle returns current title
func (m *MusicModule) GetTitle() string {
	return m.title
}

// GetPlaybackStatus returns playback status
func (m *MusicModule) GetPlaybackStatus() string {
	return m.playbackStatus
}

// IsPlaying returns whether music is playing
func (m *MusicModule) IsPlaying() bool {
	return m.isPlaying
}

// Cleanup cleans up resources
func (m *MusicModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// MusicModuleFactory is a factory for creating MusicModule instances
type MusicModuleFactory struct{}

// CreateModule creates a new MusicModule instance
func (f *MusicModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewMusicModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *MusicModuleFactory) ModuleName() string {
	return "music"
}

// DefaultConfig returns default configuration
func (f *MusicModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"host":        "localhost",
		"port":        6600,
		"show_icon":   true,
		"show_status": true,
		"max_length":  30,
		"interval":    "5s",
		"css_classes": []string{"music-module"},
	}
}

// Dependencies returns module dependencies
func (f *MusicModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &MusicModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
