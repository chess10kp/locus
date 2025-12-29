package launcher

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"github.com/chess10kp/locus/internal/config"
)

type ColorLauncher struct {
	config       *config.Config
	colorHistory *ColorHistory
}

type ColorLauncherFactory struct{}

func (f *ColorLauncherFactory) Name() string {
	return "color"
}

func (f *ColorLauncherFactory) Create(cfg *config.Config) Launcher {
	launcher := &ColorLauncher{
		config: cfg,
	}

	// Initialize color history
	dataDir := cfg.CacheDir
	if dataDir == "" {
		homeDir, _ := os.UserHomeDir()
		dataDir = filepath.Join(homeDir, ".cache", "locus")
	}

	var err error
	launcher.colorHistory, err = NewColorHistory(dataDir, 50)
	if err != nil {
		return nil
	}

	return launcher
}

func init() {
	RegisterLauncherFactory(&ColorLauncherFactory{})
}

func (l *ColorLauncher) Name() string {
	return "color"
}

func (l *ColorLauncher) CommandTriggers() []string {
	return []string{"#", "color", "colors", "hex"}
}

func (l *ColorLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *ColorLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *ColorLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	q := strings.TrimSpace(query)

	// Show history when no query
	if q == "" {
		return l.getHistoryItems()
	}

	// Parse color and show preview
	if l.isValidColor(q) {
		normalized := l.normalizeColor(q)
		return l.getColorItems(normalized)
	}

	// Search in history
	matches := l.colorHistory.SearchColors(q)
	if len(matches) > 0 {
		return l.getHistoryItems(matches...)
	}

	// Show help message
	return []*LauncherItem{
		{
			Title:      "Invalid color format",
			Subtitle:   "Try: #ff0000, f00, rgb(255,0,0), or 'red'",
			Icon:       "color-select",
			ActionData: nil,
			Launcher:   l,
		},
	}
}

func (l *ColorLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *ColorLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *ColorLauncher) Cleanup() {
}

func (l *ColorLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}

// getHistoryItems returns launcher items for color history
func (l *ColorLauncher) getHistoryItems(colors ...string) []*LauncherItem {
	if len(colors) == 0 {
		colors = l.colorHistory.GetColors()
	}

	items := make([]*LauncherItem, 0, len(colors))
	for i, color := range colors {
		// Limit to first 10 items for display
		if i >= 10 {
			break
		}

		displayColor := color
		if len(displayColor) > 0 && displayColor[0] != '#' {
			displayColor = "#" + displayColor
		}

		items = append(items, &LauncherItem{
			Title:      displayColor,
			Subtitle:   fmt.Sprintf("Click to use color"),
			Icon:       "color-select",
			ActionData: NewColorAction("save", displayColor),
			Launcher:   l,
			Metadata:   map[string]string{"color": displayColor},
		})
	}

	return items
}

// getColorItems returns launcher items for a specific color
func (l *ColorLauncher) getColorItems(color string) []*LauncherItem {
	displayColor := color
	if len(displayColor) > 0 && displayColor[0] != '#' {
		displayColor = "#" + displayColor
	}

	return []*LauncherItem{
		{
			Title:      displayColor,
			Subtitle:   "Save color to statusbar",
			Icon:       "color-select",
			ActionData: NewColorAction("save", displayColor),
			Launcher:   l,
			Metadata:   map[string]string{"color": displayColor},
		},
		{
			Title:      "Copy " + displayColor,
			Subtitle:   "Copy to clipboard",
			Icon:       "edit-copy",
			ActionData: NewColorAction("copy", displayColor),
			Launcher:   l,
			Metadata:   map[string]string{"color": displayColor},
		},
	}
}

// isValidColor checks if a color string is valid
func (l *ColorLauncher) isValidColor(color string) bool {
	color = strings.TrimSpace(color)
	if color == "" {
		return false
	}

	// Check hex color (3, 4, 6, or 8 digits)
	hexPattern := regexp.MustCompile(`^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$`)
	if hexPattern.MatchString(color) {
		return true
	}

	// Check rgb() format
	rgbPattern := regexp.MustCompile(`^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$`)
	if rgbPattern.MatchString(color) {
		matches := rgbPattern.FindStringSubmatch(color)
		if len(matches) == 4 {
			r, _ := strconv.Atoi(matches[1])
			g, _ := strconv.Atoi(matches[2])
			b, _ := strconv.Atoi(matches[3])
			return r >= 0 && r <= 255 && g >= 0 && g <= 255 && b >= 0 && b <= 255
		}
	}

	// Check rgba() format
	rgbaPattern := regexp.MustCompile(`^rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*([01]?\.?\d*)\s*\)$`)
	if rgbaPattern.MatchString(color) {
		matches := rgbaPattern.FindStringSubmatch(color)
		if len(matches) == 5 {
			r, _ := strconv.Atoi(matches[1])
			g, _ := strconv.Atoi(matches[2])
			b, _ := strconv.Atoi(matches[3])
			return r >= 0 && r <= 255 && g >= 0 && g <= 255 && b >= 0 && b <= 255
		}
	}

	// Check for named color
	namedColors := map[string]bool{
		"red": true, "green": true, "blue": true, "white": true, "black": true,
		"yellow": true, "cyan": true, "magenta": true, "gray": true, "grey": true,
		"orange": true, "purple": true, "pink": true, "brown": true,
		"transparent": true, "none": true,
		"darkred": true, "darkgreen": true, "darkblue": true, "darkgray": true, "darkgrey": true,
		"lightred": true, "lightgreen": true, "lightblue": true, "lightgray": true, "lightgrey": true,
		"aqua": true, "fuchsia": true, "lime": true, "maroon": true, "navy": true, "olive": true,
		"teal": true, "silver": true,
	}
	return namedColors[strings.ToLower(color)]
}

// normalizeColor normalizes color string to hex format
func (l *ColorLauncher) normalizeColor(color string) string {
	color = strings.TrimSpace(color)
	if color == "" {
		return ""
	}

	lowerColor := strings.ToLower(color)

	// Handle named colors
	namedColors := map[string]string{
		"red": "#ff0000", "green": "#00ff00", "blue": "#0000ff",
		"white": "#ffffff", "black": "#000000",
		"yellow": "#ffff00", "cyan": "#00ffff", "magenta": "#ff00ff",
		"gray": "#808080", "grey": "#808080",
		"orange": "#ffa500", "purple": "#800080", "pink": "#ffc0cb",
		"brown": "#a52a2a", "transparent": "#00000000",
		"darkred": "#8b0000", "darkgreen": "#006400", "darkblue": "#00008b",
		"darkgray": "#a9a9a9", "darkgrey": "#a9a9a9",
		"lightred": "#ff6b6b", "lightgreen": "#90ee90", "lightblue": "#add8e6",
		"lightgray": "#d3d3d3", "lightgrey": "#d3d3d3",
		"aqua": "#00ffff", "fuchsia": "#ff00ff", "lime": "#00ff00",
		"maroon": "#800000", "navy": "#000080", "olive": "#808000",
		"teal": "#008080", "silver": "#c0c0c0",
	}

	if hex, ok := namedColors[lowerColor]; ok {
		return hex
	}

	// Remove # prefix if present
	if len(color) > 0 && color[0] == '#' {
		color = color[1:]
	}

	// Expand 3-digit hex to 6-digit
	if len(color) == 3 {
		color = string([]byte{color[0], color[0], color[1], color[1], color[2], color[2]})
	}

	// Expand 4-digit hex to 8-digit
	if len(color) == 4 {
		color = string([]byte{color[0], color[0], color[1], color[1], color[2], color[2], color[3], color[3]})
	}

	return "#" + strings.ToLower(color)
}

// GetColor returns the parsed color for preview
func (l *ColorLauncher) GetColor(query string) (string, bool) {
	q := strings.TrimSpace(query)
	if q == "" {
		return "", false
	}

	if l.isValidColor(q) {
		return l.normalizeColor(q), true
	}

	return "", false
}

// AddToHistory adds a color to history
func (l *ColorLauncher) AddToHistory(color string) {
	l.colorHistory.Add(color)
}
