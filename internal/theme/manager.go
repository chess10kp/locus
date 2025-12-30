package theme

import (
	"fmt"
	"log"
	"os"
	"path/filepath"

	"github.com/chess10kp/locus/internal/config"
	"github.com/gotk3/gotk3/gdk"
	"github.com/gotk3/gotk3/gtk"
)

type ThemeManager struct {
	config     *config.ThemeConfig
	engine     *ThemeEngine
	gtkScreen  *gdk.Screen
	providers  map[string]*gtk.CssProvider
	configPath string
}

func NewThemeManager(cfg *config.ThemeConfig) (*ThemeManager, error) {
	screen, err := gdk.ScreenGetDefault()
	if err != nil || screen == nil {
		return nil, fmt.Errorf("failed to get default screen: %w", err)
	}

	providers := make(map[string]*gtk.CssProvider)

	currentTheme, exists := cfg.Themes[cfg.CurrentTheme]
	if !exists {
		return nil, fmt.Errorf("current theme '%s' not found in themes", cfg.CurrentTheme)
	}

	engine := NewThemeEngine(&currentTheme)

	manager := &ThemeManager{
		config:     cfg,
		engine:     engine,
		gtkScreen:  screen,
		providers:  providers,
		configPath: "",
	}

	return manager, nil
}

func (m *ThemeManager) ApplyTheme(themeName string) error {
	themeData, exists := m.config.Themes[themeName]
	if !exists {
		return fmt.Errorf("theme '%s' not found", themeName)
	}

	if err := themeData.Validate(); err != nil {
		return fmt.Errorf("invalid theme '%s': %w", themeName, err)
	}

	if err := m.engine.ReloadTheme(&themeData); err != nil {
		return fmt.Errorf("failed to reload theme: %w", err)
	}

	if err := m.RefreshCSS(); err != nil {
		return fmt.Errorf("failed to refresh CSS: %w", err)
	}

	m.config.CurrentTheme = themeName

	log.Printf("Applied theme: %s", themeName)
	return nil
}

func (m *ThemeManager) RefreshCSS() error {
	if err := m.loadGlobalCSS(); err != nil {
		return err
	}

	if err := m.loadStatusBarCSS(); err != nil {
		return err
	}

	if err := m.loadLauncherCSS(); err != nil {
		return err
	}

	if err := m.loadLockscreenCSS(); err != nil {
		return err
	}

	return nil
}

func (m *ThemeManager) loadGlobalCSS() error {
	globalCSS := m.engine.GenerateGlobalCSS()

	provider, _ := gtk.CssProviderNew()
	if err := provider.LoadFromData(globalCSS); err != nil {
		return fmt.Errorf("failed to load global CSS: %w", err)
	}

	m.providers["global"] = provider
	gtk.AddProviderForScreen(m.gtkScreen, provider, gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

	return nil
}

func (m *ThemeManager) loadStatusBarCSS() error {
	statusbarCSS := m.engine.GenerateStatusBarCSS()

	provider, _ := gtk.CssProviderNew()
	if err := provider.LoadFromData(statusbarCSS); err != nil {
		return fmt.Errorf("failed to load statusbar CSS: %w", err)
	}

	m.providers["statusbar"] = provider
	gtk.AddProviderForScreen(m.gtkScreen, provider, gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

	return nil
}

func (m *ThemeManager) loadLauncherCSS() error {
	launcherCSS := m.engine.GenerateLauncherCSS()

	provider, _ := gtk.CssProviderNew()
	if err := provider.LoadFromData(launcherCSS); err != nil {
		return fmt.Errorf("failed to load launcher CSS: %w", err)
	}

	m.providers["launcher"] = provider
	gtk.AddProviderForScreen(m.gtkScreen, provider, gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

	return nil
}

func (m *ThemeManager) loadLockscreenCSS() error {
	lockscreenCSS := m.engine.GenerateLockscreenCSS()

	provider, _ := gtk.CssProviderNew()
	if err := provider.LoadFromData(lockscreenCSS); err != nil {
		return fmt.Errorf("failed to load lockscreen CSS: %w", err)
	}

	m.providers["lockscreen"] = provider
	gtk.AddProviderForScreen(m.gtkScreen, provider, gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

	return nil
}

func (m *ThemeManager) ListAvailableThemes() []string {
	themes := make([]string, 0, len(m.config.Themes))
	for name := range m.config.Themes {
		themes = append(themes, name)
	}
	return themes
}

func (m *ThemeManager) GetCurrentTheme() string {
	return m.config.CurrentTheme
}

func (m *ThemeManager) GetTheme(name string) (*config.Theme, error) {
	theme, exists := m.config.Themes[name]
	if !exists {
		return nil, fmt.Errorf("theme '%s' not found", name)
	}
	return &theme, nil
}

func (m *ThemeManager) AddTheme(name string, theme config.Theme) error {
	if err := theme.Validate(); err != nil {
		return fmt.Errorf("invalid theme: %w", err)
	}

	m.config.Themes[name] = theme
	return nil
}

func (m *ThemeManager) LoadExternalTheme(path string) error {
	_, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("failed to read theme file: %w", err)
	}

	var externalTheme config.Theme
	if err := externalTheme.Validate(); err != nil {
		return fmt.Errorf("invalid external theme: %w", err)
	}

	themeName := filepath.Base(path)
	themeName = themeName[:len(themeName)-len(filepath.Ext(themeName))]

	return m.AddTheme(themeName, externalTheme)
}

func (m *ThemeManager) LoadThemesFromDirectory(dirPath string) error {
	files, err := os.ReadDir(dirPath)
	if err != nil {
		return fmt.Errorf("failed to read theme directory: %w", err)
	}

	for _, file := range files {
		if file.IsDir() {
			continue
		}

		if filepath.Ext(file.Name()) != ".toml" {
			continue
		}

		path := filepath.Join(dirPath, file.Name())
		if err := m.LoadExternalTheme(path); err != nil {
			log.Printf("Warning: Failed to load theme from %s: %v", path, err)
		}
	}

	return nil
}

func (m *ThemeManager) GetEngine() *ThemeEngine {
	return m.engine
}

func (m *ThemeManager) SetConfigPath(path string) {
	m.configPath = path
}

func (m *ThemeManager) SaveCurrentTheme() error {
	if m.configPath == "" {
		return fmt.Errorf("config path not set")
	}

	return nil
}

func (m *ThemeManager) ReloadConfig(newConfig *config.ThemeConfig) error {
	if err := newConfig.Validate(); err != nil {
		return fmt.Errorf("invalid theme config: %w", err)
	}

	m.config = newConfig

	return m.ApplyTheme(m.config.CurrentTheme)
}
