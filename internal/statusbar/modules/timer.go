package modules

import (
	"log"
	"strings"

	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/statusbar"
)

type TimerModule struct {
	*statusbar.BaseModule
	widget  *gtk.Label
	display string
}

func NewTimerModule() *TimerModule {
	return &TimerModule{
		BaseModule: statusbar.NewBaseModule("timer", statusbar.UpdateModeOnDemand),
		widget:     nil,
		display:    "",
	}
}

func (m *TimerModule) CreateWidget() (gtk.IWidget, error) {
	label, err := gtk.LabelNew(m.display)
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

func (m *TimerModule) UpdateWidget(widget gtk.IWidget) error {
	if widget == nil {
		return nil
	}

	label, ok := widget.(*gtk.Label)
	if !ok {
		return nil
	}

	label.SetText(m.display)

	return nil
}

func (m *TimerModule) Initialize(config map[string]interface{}) error {
	log.Printf("[TIMER-MODULE] Initializing timer module")
	if err := m.BaseModule.Initialize(config); err != nil {
		log.Printf("[TIMER-MODULE] Failed to initialize base module: %v", err)
		return err
	}

	m.SetCSSClasses([]string{"timer-module"})

	m.SetIPCHandler(func(message string) bool {
		log.Printf("[TIMER-MODULE] Received IPC message: %s", message)
		if strings.HasPrefix(message, "timer:") {
			timerMsg := strings.TrimPrefix(message, "timer:")
			if timerMsg == "clear" {
				log.Printf("[TIMER-MODULE] Clearing timer display")
				m.display = ""
			} else {
				log.Printf("[TIMER-MODULE] Setting timer display to: %s", timerMsg)
				m.display = "Timer: " + timerMsg
			}
			return true
		}
		return false
	})

	log.Printf("[TIMER-MODULE] Timer module initialized successfully")
	return nil
}

func (m *TimerModule) Cleanup() error {
	return m.BaseModule.Cleanup()
}

type TimerModuleFactory struct{}

func (f *TimerModuleFactory) CreateModule(config map[string]interface{}) (statusbar.Module, error) {
	module := NewTimerModule()
	if err := module.Initialize(config); err != nil {
		return nil, err
	}
	return module, nil
}

func (f *TimerModuleFactory) ModuleName() string {
	return "timer"
}

func (f *TimerModuleFactory) DefaultConfig() map[string]interface{} {
	return map[string]interface{}{
		"css_classes": []string{"timer-module"},
	}
}

func (f *TimerModuleFactory) Dependencies() []string {
	return []string{}
}

func init() {
	registry := statusbar.DefaultRegistry()
	factory := &TimerModuleFactory{}
	if err := registry.RegisterFactory(factory); err != nil {
		panic(err)
	}
}
