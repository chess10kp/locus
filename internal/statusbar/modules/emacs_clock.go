package modules

import (
	"encoding/json"
	"log"
	"os/exec"
	"strings"
	"time"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

// EmacsClockInfo represents clock information from Emacs
type EmacsClockInfo struct {
	Task string `json:"task"`
	Time string `json:"time"`
}

// getEmacsClockInfo gets the current Emacs org-mode clock information
func getEmacsClockInfo() (*EmacsClockInfo, error) {
	emacsScript := `
(let ((inhibit-message t)
      (message-log-max nil))
  (with-temp-message ""
    (if (org-clock-is-active)
        (let* ((clock-string-raw (org-clock-get-clock-string))
               (plain (substring-no-properties clock-string-raw))
               (bracket1 (string-search "[" plain))
               (bracket2 (string-search "]" plain))
               (paren1 (string-search "(" plain))
               (paren2 (string-search ")" plain))
               (time-str (if (and bracket1 bracket2)
                             (substring plain (+ bracket1 1) bracket2)
                             ""))
               (task-name (if (and paren1 paren2)
                              (substring plain (+ paren1 1) paren2)
                              "")))
          (princ (json-encode ` + "`" + `((task . ,task-name) (time . ,time-str)))))
      (princ "null"))))
`

	cmd := exec.Command("emacsclient", "--quiet", "-e", emacsScript)
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}

	outputStr := strings.TrimSpace(string(output))

	if outputStr == "null" || outputStr == "" {
		return nil, nil
	}

	if strings.HasPrefix(outputStr, `"`) && strings.HasSuffix(outputStr, `"`) {
		unquoted, err := unescapeJSONString(outputStr[1 : len(outputStr)-1])
		if err != nil {
			return nil, err
		}
		outputStr = unquoted
	}

	var info EmacsClockInfo
	if err := json.Unmarshal([]byte(outputStr), &info); err != nil {
		return nil, err
	}

	if info.Task == "" && info.Time == "" {
		return nil, nil
	}

	return &info, nil
}

// unescapeJSONString unescapes a JSON string literal
func unescapeJSONString(s string) (string, error) {
	var unescaped string
	if err := json.Unmarshal([]byte(`"`+s+`"`), &unescaped); err != nil {
		return "", err
	}
	return unescaped, nil
}

// EmacsClockModule displays the current Emacs org-mode clocked task
type EmacsClockModule struct {
	*statusbar.BaseModule
	widget       *gtk.Label
	clockInfo    *EmacsClockInfo
	fallbackText string
	interval     time.Duration
}

// NewEmacsClockModule creates a new Emacs clock module
func NewEmacsClockModule() *EmacsClockModule {
	return &EmacsClockModule{
		BaseModule:   statusbar.NewBaseModule("emacs_clock", statusbar.UpdateModePeriodic),
		widget:       nil,
		clockInfo:    nil,
		fallbackText: "",
		interval:     10 * time.Second,
	}
}

// CreateWidget creates an Emacs clock label widget
func (m *EmacsClockModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.fallbackText)
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

// UpdateWidget updates Emacs clock widget
func (m *EmacsClockModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	info, err := getEmacsClockInfo()
	if err != nil {
		log.Printf("Failed to get Emacs clock info: %v", err)
		label.SetText(m.fallbackText)
		return nil
	}

	m.clockInfo = info

	if info != nil && info.Task != "" {
		if info.Time != "" {
			label.SetText("org: " + info.Task + ": " + info.Time)
		} else {
			label.SetText("org: " + info.Task)
		}
	} else {
		label.SetText(m.fallbackText)
	}

	return nil
}

// Initialize initializes the module with configuration
func (m *EmacsClockModule) Initialize(config map[string]interface{}) error {
	if err := m.BaseModule.Initialize(config); err != nil {
		return err
	}

	if fallbackText, ok := config["fallback_text"].(string); ok {
		m.fallbackText = fallbackText
	}

	if interval, ok := config["interval"].(string); ok {
		if duration, err := time.ParseDuration(interval); err == nil {
			m.interval = duration
		}
	}

	m.SetCSSClasses([]string{"emacs-clock-module"})

	return nil
}

// GetClockInfo returns the current clock information
func (m *EmacsClockModule) GetClockInfo() *EmacsClockInfo {
	return m.clockInfo
}

// SetFallbackText sets the fallback text to display when no clock is active
func (m *EmacsClockModule) SetFallbackText(text string) {
	m.fallbackText = text
}

// Cleanup cleans up resources
func (m *EmacsClockModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

// EmacsClockModuleFactory is a factory for creating EmacsClockModule instances
type EmacsClockModuleFactory struct{}

// CreateModule creates a new EmacsClockModule instance
func (f *EmacsClockModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewEmacsClockModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

// ModuleName returns module name
func (f *EmacsClockModuleFactory) ModuleName() string {
	return "emacs_clock"
}

// DefaultConfig returns default configuration
func (f *EmacsClockModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"fallback_text": "",
		"interval":      "10s",
		"css_classes":   []string{"emacs-clock-module"},
	}
}

// Dependencies returns module dependencies
func (f *EmacsClockModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &EmacsClockModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
