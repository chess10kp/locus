package launcher

import (
	"testing"

	"github.com/sigma/locus-go/internal/config"
)

func TestLauncherRegistration(t *testing.T) {
	cfg := &config.Config{}
	registry := NewLauncherRegistry(cfg)

	err := registry.LoadBuiltIn()
	if err != nil {
		t.Fatalf("Failed to load built-in launchers: %v", err)
	}

	launchers := registry.GetAllLaunchers()
	if len(launchers) < 8 {
		t.Errorf("Expected at least 8 launchers, got %d", len(launchers))
	}

	launcherNames := make(map[string]bool)
	for _, l := range launchers {
		launcherNames[l.Name()] = true

		if len(l.CommandTriggers()) == 0 {
			t.Errorf("Launcher %s has no command triggers", l.Name())
		}
	}

	expectedLaunchers := []string{
		"shell", "web", "calc", "brightness",
		"screenshot", "lock", "timer", "kill",
		"focus", "wallpaper",
	}

	for _, name := range expectedLaunchers {
		if !launcherNames[name] {
			t.Errorf("Expected launcher '%s' not registered", name)
		}
	}
}

func TestLauncherQueryParsing(t *testing.T) {
	cfg := &config.Config{}
	registry := NewLauncherRegistry(cfg)
	registry.LoadBuiltIn()

	testCases := []struct {
		query     string
		launcher  string
		wantFound bool
	}{
		{">sh ls", "shell", true},
		{"web:google.com", "web", true},
		{"calc:2+2", "calc", true},
		{">brightness up", "brightness", true},
		{">shot", "screenshot", true},
		{">lock", "lock", true},
		{">timer 5m", "timer", true},
		{">kill", "kill", true},
		{">focus left", "focus", true},
		{">wallpaper", "wallpaper", true},
	}

	for _, tc := range testCases {
		_, l, _ := registry.FindLauncherForInput(tc.query)
		found := (l != nil)

		if found != tc.wantFound {
			t.Errorf("Query '%s': expected found=%v, got found=%v", tc.query, tc.wantFound, found)
		}

		if found && l.Name() != tc.launcher {
			t.Errorf("Query '%s': expected launcher '%s', got '%s'", tc.query, tc.launcher, l.Name())
		}
	}
}
