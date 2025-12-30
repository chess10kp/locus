package theme

import (
	"fmt"
	"log"

	"github.com/chess10kp/locus/internal/config"
)

type ThemeEngine struct {
	theme *config.Theme
}

func NewThemeEngine(theme *config.Theme) *ThemeEngine {
	return &ThemeEngine{
		theme: theme,
	}
}

func (e *ThemeEngine) SetTheme(theme *config.Theme) {
	e.theme = theme
}

func (e *ThemeEngine) GetTheme() *config.Theme {
	return e.theme
}

func (e *ThemeEngine) GetSemanticColor(colorName string) string {
	switch colorName {
	case "background":
		return e.theme.Colors.Background
	case "foreground":
		return e.theme.Colors.Foreground
	case "primary":
		return e.theme.Colors.Primary
	case "secondary":
		return e.theme.Colors.Secondary
	case "accent":
		return e.theme.Colors.Accent
	case "success":
		return e.theme.Colors.Success
	case "warning":
		return e.theme.Colors.Warning
	case "error":
		return e.theme.Colors.Error
	case "info":
		return e.theme.Colors.Info
	case "border":
		return e.theme.Colors.Border
	case "muted":
		return e.theme.Colors.Muted
	case "disabled":
		return e.theme.Colors.Disabled
	case "statusbar-background":
		return e.theme.Colors.StatusbarBackground
	case "launcher-background":
		return e.theme.Colors.LauncherBackground
	case "lockscreen-background":
		return e.theme.Colors.LockscreenBackground
	default:
		log.Printf("Warning: Unknown semantic color '%s', returning foreground", colorName)
		return e.theme.Colors.Foreground
	}
}

func (e *ThemeEngine) GenerateGlobalCSS() string {
	c := e.theme.Colors
	t := e.theme.Typography

	return fmt.Sprintf(`
* {
    font-family: "%s", monospace;
    font-size: %dpx;
    font-weight: %s;
    margin: 0;
    padding: 0;
    transition: opacity 0.2s ease;
}

label {
    color: %s;
    font-size: %dpx;
    font-family: "%s", monospace;
    margin: 0;
    padding: 0;
    transition: opacity 0.2s ease;
}

window {
    background-color: %s;
    border-bottom: 1px solid %s;
}

#main-box, box {
    background-color: %s;
}

.separator {
    color: %s;
    font-size: 18px;
    font-family: monospace;
}
`,
		t.FontFamily,
		t.FontSize,
		t.FontWeight,
		c.Muted,
		t.FontSize,
		t.FontFamily,
		c.Background,
		c.Border,
		c.Background,
		c.Border,
	)
}

func (e *ThemeEngine) GenerateStatusBarCSS() string {
	c := e.theme.Colors
	t := e.theme.Typography
	s := e.theme.Spacing

	return fmt.Sprintf(`
#statusbar {
    background-color: %s;
    color: %s;
    padding: %dpx;
    font-family: "%s", monospace;
    font-size: %dpx;
    font-weight: %s;
}

.text-muted {
    color: %s;
}

.text-error {
    color: %s;
}

.text-warning {
    color: %s;
}

.text-success {
    color: %s;
}

.text-info {
    color: %s;
}

.text-primary {
    color: %s;
}

.battery-critical {
    color: %s;
}

.battery-low {
    color: %s;
}
 `,
		c.StatusbarBackground,
		c.Foreground,
		s.SM/2,
		t.FontFamily,
		t.FontSize,
		t.FontWeight,
		c.Muted,
		c.Error,
		c.Warning,
		c.Success,
		c.Info,
		c.Primary,
		c.Error,
		c.Warning,
	)
}

func (e *ThemeEngine) GenerateLauncherCSS() string {
	c := e.theme.Colors
	t := e.theme.Typography
	b := e.theme.BorderRadius
	s := e.theme.Spacing

	bgColor := c.LauncherBackground
	if len(bgColor) == 7 && bgColor[0] == '#' {
		bgColor = bgColor + "f2"
	}

	return fmt.Sprintf(`
#launcher-window {
    background-color: %s;
    color: %s;
    border-radius: %dpx;
    border: 1px solid %s;
}

#animation-container {
    transition: opacity 300ms ease-out, transform 300ms ease-out !important;
    opacity: 1 !important;
    transform: scale(1) !important;
}

#animation-container.animating-in {
    opacity: 0 !important;
    transform: scale(0.8) !important;
}

#launcher-entry {
    background-color: %s;
    color: %s;
    padding: %dpx %dpx;
    border: none;
    border-bottom: 1px solid %s;
    font-family: %s, monospace;
    font-size: %dpx;
    font-weight: %s;
    border-radius: %dpx;
}

#launcher-entry:focus {
    border-bottom: 2px solid %s;
}

#result-list {
    background-color: transparent;
}

#list-row {
    padding: %dpx %dpx;
    border-bottom: none;
    min-height: %dpx;
    background-color: transparent;
}

#list-row:selected {
    background-color: %s;
    color: %s;
}

#list-row:hover {
    background-color: %s;
}

#result-title {
    font-size: 16px;
    font-weight: bold;
}

#result-subtitle {
    font-size: 11px;
}

#badges-box {
    background-color: %s;
    padding: %dpx %dpx;
    border-radius: %dpx;
    margin-top: %dpx;
    font-size: 12px;
}

#badges-box label {
    color: %s;
    font-family: %s, monospace;
    padding: 0px %dpx;
}

#footer-box {
    background-color: %s;
    padding: %dpx %dpx;
    border-radius: %dpx;
    margin: %dpx;
    font-size: %dpx;
}

#footer-box label {
    color: %s;
    font-family: %s, monospace;
    font-size: %dpx;
    text-align: left;
}
`,
		bgColor,
		c.Foreground,
		b.Medium,
		c.Border,

		e.adjustBrightness(c.Background, -0.1),
		c.Foreground,
		s.MD,
		s.SM,
		c.Border,
		t.FontFamily,
		t.FontSize,
		t.FontWeight,
		b.Small,

		c.Primary,

		s.SM,
		s.SM,
		s.MD*2,

		c.Primary,
		c.Background,

		e.adjustBrightness(c.Primary, -0.3),

		e.adjustBrightness(c.Background, -0.1),
		s.SM,
		s.SM,
		b.Small,
		s.XS,
		c.Muted,
		t.FontFamily,
		s.XS,

		e.adjustBrightness(c.Background, -0.1),
		s.SM,
		s.SM,
		b.Small,
		s.XS,
		t.FontSize,

		c.Muted,
		t.FontFamily,
		t.FontSize,
	)
}

func (e *ThemeEngine) GenerateLockscreenCSS() string {
	c := e.theme.Colors
	b := e.theme.BorderRadius
	t := e.theme.Typography

	return fmt.Sprintf(`
#lockscreen-container {
    background-color: %s;
}

#lockscreen-window {
    background-color: %s;
}

 #lockscreen-entry {
    background-color: %s;
    color: %s;
    border: 2px solid %s;
    border-radius: %dpx;
    padding: 12px;
    font-size: %dpx;
    font-family: %s;
    min-width: 300px;
}

#lockscreen-entry:focus {
    border-color: %s;
    background-color: %s;
}

#lockscreen-status {
    color: %s;
    font-family: %s;
    padding: %dpx;
    min-height: 30px;
}

#lockscreen-status.error {
    color: %s;
}

#lockscreen-status.success {
    color: %s;
}

#lockscreen-status.warning {
    color: %s;
}

#lockscreen-label {
    color: %s;
    font-family: %s;
    font-weight: bold;
    font-size: 24px;
}

#lockscreen-clock {
    color: %s;
    font-family: %s;
    font-weight: bold;
    font-size: 80px;
}
 `,
		c.LockscreenBackground,
		c.LockscreenBackground,
		c.LockscreenBackground,
		c.Foreground,

		e.adjustBrightness(c.Background, -0.1),
		b.Medium,
		24,
		t.FontFamily,

		c.Primary,
		e.adjustBrightness(c.Background, -0.15),

		c.Foreground,
		t.FontFamily,
		15,

		c.Error,
		c.Success,
		c.Warning,

		c.Foreground,
		t.FontFamily,

		c.Foreground,
		t.FontFamily,
	)
}

func (e *ThemeEngine) ReloadTheme(theme *config.Theme) error {
	if err := theme.Validate(); err != nil {
		return fmt.Errorf("invalid theme: %w", err)
	}

	e.theme = theme
	return nil
}

func (e *ThemeEngine) adjustBrightness(hexColor string, factor float64) string {
	if len(hexColor) != 7 || hexColor[0] != '#' {
		return hexColor
	}

	var r, g, b int
	fmt.Sscanf(hexColor[1:], "%02x%02x%02x", &r, &g, &b)

	r = int(float64(r) * (1 + factor))
	g = int(float64(g) * (1 + factor))
	b = int(float64(b) * (1 + factor))

	if r > 255 {
		r = 255
	} else if r < 0 {
		r = 0
	}

	if g > 255 {
		g = 255
	} else if g < 0 {
		g = 0
	}

	if b > 255 {
		b = 255
	} else if b < 0 {
		b = 0
	}

	return fmt.Sprintf("#%02x%02x%02x", r, g, b)
}

var globalEngine *ThemeEngine

func SetGlobalEngine(engine *ThemeEngine) {
	globalEngine = engine
}

func GetGlobalEngine() *ThemeEngine {
	return globalEngine
}
