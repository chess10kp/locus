package core

import (
	"github.com/sigma/locus-go/internal/config"
)

// Stub window/widget types
type WidgetStub struct{}

type StatusBar struct {
	config      *config.Config
	visible     bool
	initialized bool
}

type Launcher struct {
	config      *config.Config
	visible     bool
	hidden      bool
	initialized bool
}

// NewStatusBar creates a status bar
func NewStatusBar(cfg *config.Config) (*StatusBar, error) {
	return &StatusBar{
		config:      cfg,
		visible:     false,
		initialized: true,
	}, nil
}

// NewLauncher creates a launcher
func NewLauncher(cfg *config.Config) (*Launcher, error) {
	return &Launcher{
		config:      cfg,
		visible:     false,
		hidden:      true,
		initialized: true,
	}, nil
}

// Show/Hide methods
func (s *StatusBar) Show()    { s.visible = true }
func (s *StatusBar) Hide()    { s.visible = false }
func (s *StatusBar) Cleanup() { s.initialized = false }

func (l *Launcher) Present() { l.visible = true; l.hidden = false }
func (l *Launcher) Hide()    { l.visible = false; l.hidden = true }
func (l *Launcher) Cleanup() { l.initialized = false }
