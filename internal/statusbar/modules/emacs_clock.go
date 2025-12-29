package modules

import (
	"context"
	"encoding/json"
	"log"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/chess10kp/locus/internal/statusbar"
	"github.com/gotk3/gotk3/glib"
	"github.com/gotk3/gotk3/gtk"
)

type EmacsClockInfo struct {
	Task string `json:"task"`
	Time string `json:"time"`
}

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

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	cmd := exec.CommandContext(ctx, "emacsclient", "--quiet", "-e", emacsScript)
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

func unescapeJSONString(s string) (string, error) {
	var unescaped string
	if err := json.Unmarshal([]byte(`"`+s+`"`), &unescaped); err != nil {
		return "", err
	}
	return unescaped, nil
}

type EmacsClockModule struct {
	*statusbar.BaseModule
	widget       *gtk.Label
	clockInfo    *EmacsClockInfo
	fallbackText string
	interval     time.Duration
	mu           sync.Mutex
	lastUpdate   time.Time
}

func NewEmacsClockModule() *EmacsClockModule {
	return &EmacsClockModule{
		BaseModule:   statusbar.NewBaseModule("emacs_clock", statusbar.UpdateModePeriodic),
		widget:       nil,
		clockInfo:    nil,
		fallbackText: "",
		interval:     30 * time.Second,
	}
}

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

func (m *EmacsClockModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	go func() {
		startTime := time.Now()
		info, err := getEmacsClockInfo()

		glib.IdleAdd(func() {
			m.mu.Lock()
			defer m.mu.Unlock()

			if err != nil {
				log.Printf("[EMACS-CLOCK] Failed to get Emacs clock info: %v", err)
				label.SetText(m.fallbackText)
				m.clockInfo = nil
				m.lastUpdate = time.Now()
				return
			}

			m.clockInfo = info
			m.lastUpdate = time.Now()

			if info != nil && info.Task != "" {
				if info.Time != "" {
					label.SetText(info.Task + ": " + info.Time)
				} else {
					label.SetText(info.Task)
				}
			} else {
				label.SetText(m.fallbackText)
			}

			duration := time.Since(startTime)
			if duration > 500*time.Millisecond {
				log.Printf("[EMACS-CLOCK] WARNING: Update took %v (slow!)", duration)
			}
		})
	}()

	return nil
}

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

func (m *EmacsClockModule) GetClockInfo() *EmacsClockInfo {
	return m.clockInfo
}

func (m *EmacsClockModule) SetFallbackText(text string) {
	m.fallbackText = text
}

func (m *EmacsClockModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

type EmacsClockModuleFactory struct{}

func (f *EmacsClockModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewEmacsClockModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

func (f *EmacsClockModuleFactory) ModuleName() string {
	return "emacs_clock"
}

func (f *EmacsClockModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"fallback_text": "",
		"interval":      "10s",
		"css_classes":   []string{"emacs-clock-module"},
	}
}

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
