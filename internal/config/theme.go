package config

import (
	"fmt"
	"regexp"
	"strings"
)

type ColorPalette struct {
	Background           string `toml:"background"`
	Foreground           string `toml:"foreground"`
	Primary              string `toml:"primary"`
	Secondary            string `toml:"secondary"`
	Accent               string `toml:"accent"`
	Success              string `toml:"success"`
	Warning              string `toml:"warning"`
	Error                string `toml:"error"`
	Info                 string `toml:"info"`
	Border               string `toml:"border"`
	Muted                string `toml:"muted"`
	Disabled             string `toml:"disabled"`
	StatusbarBackground  string `toml:"statusbar_background"`
	LauncherBackground   string `toml:"launcher_background"`
	LockscreenBackground string `toml:"lockscreen_background"`
}

type Typography struct {
	FontFamily string `toml:"font_family"`
	FontSize   int    `toml:"font_size"`
	FontWeight string `toml:"font_weight"`
}

type Spacing struct {
	XS int `toml:"xs"`
	SM int `toml:"sm"`
	MD int `toml:"md"`
	LG int `toml:"lg"`
	XL int `toml:"xl"`
}

type BorderRadius struct {
	Small  int `toml:"small"`
	Medium int `toml:"medium"`
	Large  int `toml:"large"`
	Full   int `toml:"full"`
}

type Theme struct {
	Name         string       `toml:"name"`
	Colors       ColorPalette `toml:"colors"`
	Typography   Typography   `toml:"typography"`
	Spacing      Spacing      `toml:"spacing"`
	BorderRadius BorderRadius `toml:"border_radius"`
}

type ThemeConfig struct {
	CurrentTheme string           `toml:"current_theme"`
	Themes       map[string]Theme `toml:"themes"`
}

func DefaultSpacing() Spacing {
	return Spacing{
		XS: 4,
		SM: 8,
		MD: 16,
		LG: 24,
		XL: 32,
	}
}

func DefaultBorderRadius() BorderRadius {
	return BorderRadius{
		Small:  4,
		Medium: 8,
		Large:  12,
		Full:   999,
	}
}

func DefaultTypography() Typography {
	return Typography{
		FontFamily: "Victor Mono, monospace",
		FontSize:   16,
		FontWeight: "bold",
	}
}

func DefaultColors() ColorPalette {
	return ColorPalette{
		Background:           "#282828",
		Foreground:           "#ebdbb2",
		Primary:              "#fe8019",
		Secondary:            "#d3869b",
		Accent:               "#fabd2f",
		Success:              "#98971a",
		Warning:              "#d79921",
		Error:                "#cc241d",
		Info:                 "#458588",
		Border:               "#3c3836",
		Muted:                "#928374",
		Disabled:             "#665c54",
		StatusbarBackground:  "#1e1e2e",
		LauncherBackground:   "#0e1419",
		LockscreenBackground: "#0e1419",
	}
}

func DefaultTheme() Theme {
	return Theme{
		Name:         "gruvbox-dark",
		Colors:       DefaultColors(),
		Typography:   DefaultTypography(),
		Spacing:      DefaultSpacing(),
		BorderRadius: DefaultBorderRadius(),
	}
}

func (t *Theme) Validate() error {
	if t.Name == "" {
		return fmt.Errorf("theme name cannot be empty")
	}

	if err := t.validateColors(); err != nil {
		return fmt.Errorf("invalid colors: %w", err)
	}

	if err := t.validateTypography(); err != nil {
		return fmt.Errorf("invalid typography: %w", err)
	}

	if err := t.validateSpacing(); err != nil {
		return fmt.Errorf("invalid spacing: %w", err)
	}

	if err := t.validateBorderRadius(); err != nil {
		return fmt.Errorf("invalid border_radius: %w", err)
	}

	return nil
}

func (t *Theme) validateColors() error {
	colors := []string{
		t.Colors.Background,
		t.Colors.Foreground,
		t.Colors.Primary,
		t.Colors.Secondary,
		t.Colors.Accent,
		t.Colors.Success,
		t.Colors.Warning,
		t.Colors.Error,
		t.Colors.Info,
		t.Colors.Border,
		t.Colors.Muted,
		t.Colors.Disabled,
		t.Colors.StatusbarBackground,
		t.Colors.LauncherBackground,
		t.Colors.LockscreenBackground,
	}

	for _, color := range colors {
		if color == "" {
			continue
		}
		if !isValidHexColor(color) && !isValidRGBA(color) {
			return fmt.Errorf("invalid color format: %s", color)
		}
	}

	return nil
}

func isValidHexColor(color string) bool {
	hexRegex := regexp.MustCompile(`^#[0-9a-fA-F]{6}$`)
	return hexRegex.MatchString(color)
}

func isValidRGBA(color string) bool {
	rgbaRegex := regexp.MustCompile(`^rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[0-9.]+\s*)?\)$`)
	return rgbaRegex.MatchString(color)
}

func (t *Theme) validateTypography() error {
	if t.Typography.FontFamily == "" {
		return fmt.Errorf("font_family cannot be empty")
	}

	if t.Typography.FontSize < 8 || t.Typography.FontSize > 72 {
		return fmt.Errorf("font_size must be between 8 and 72, got: %d", t.Typography.FontSize)
	}

	validWeights := map[string]bool{
		"normal": true, "bold": true, "bolder": true, "lighter": true,
		"100": true, "200": true, "300": true, "400": true,
		"500": true, "600": true, "700": true, "800": true, "900": true,
	}

	if !validWeights[strings.ToLower(t.Typography.FontWeight)] {
		return fmt.Errorf("invalid font_weight: %s", t.Typography.FontWeight)
	}

	return nil
}

func (t *Theme) validateSpacing() error {
	if t.Spacing.XS < 0 || t.Spacing.XS > 64 {
		return fmt.Errorf("spacing xs must be between 0 and 64")
	}
	if t.Spacing.SM < 0 || t.Spacing.SM > 64 {
		return fmt.Errorf("spacing sm must be between 0 and 64")
	}
	if t.Spacing.MD < 0 || t.Spacing.MD > 128 {
		return fmt.Errorf("spacing md must be between 0 and 128")
	}
	if t.Spacing.LG < 0 || t.Spacing.LG > 128 {
		return fmt.Errorf("spacing lg must be between 0 and 128")
	}
	if t.Spacing.XL < 0 || t.Spacing.XL > 256 {
		return fmt.Errorf("spacing xl must be between 0 and 256")
	}
	return nil
}

func (t *Theme) validateBorderRadius() error {
	if t.BorderRadius.Small < 0 || t.BorderRadius.Small > 32 {
		return fmt.Errorf("border_radius small must be between 0 and 32")
	}
	if t.BorderRadius.Medium < 0 || t.BorderRadius.Medium > 32 {
		return fmt.Errorf("border_radius medium must be between 0 and 32")
	}
	if t.BorderRadius.Large < 0 || t.BorderRadius.Large > 48 {
		return fmt.Errorf("border_radius large must be between 0 and 48")
	}
	if t.BorderRadius.Full < 0 || t.BorderRadius.Full > 9999 {
		return fmt.Errorf("border_radius full must be between 0 and 9999")
	}
	return nil
}

func (tc *ThemeConfig) Validate() error {
	if tc.CurrentTheme == "" {
		return fmt.Errorf("current_theme cannot be empty")
	}

	if _, exists := tc.Themes[tc.CurrentTheme]; !exists {
		return fmt.Errorf("current_theme '%s' not found in themes", tc.CurrentTheme)
	}

	for name, theme := range tc.Themes {
		if err := theme.Validate(); err != nil {
			return fmt.Errorf("invalid theme '%s': %w", name, err)
		}
	}

	return nil
}

func DefaultThemeConfig() ThemeConfig {
	presets := GetBuiltinThemes()
	return ThemeConfig{
		CurrentTheme: "gruvbox-dark",
		Themes:       presets,
	}
}
