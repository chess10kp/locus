package config

import (
	"fmt"
	"os"
	"os/user"
	"path/filepath"

	"github.com/pelletier/go-toml/v2"
)

type Config struct {
	AppName      string             `toml:"app_name"`
	AppID        string             `toml:"app_id"`
	SocketPath   string             `toml:"socket_path"`
	CacheDir     string             `toml:"cache_dir"`
	ConfigDir    string             `toml:"config_dir"`
	StatusBar    StatusBarConfig    `toml:"status_bar"`
	Launcher     LauncherConfig     `toml:"launcher"`
	Notification NotificationConfig `toml:"notification"`
	FileSearch   FileSearchConfig   `toml:"file_search"`
}

type StatusBarLayout struct {
	Left   []string `toml:"left"`
	Middle []string `toml:"middle"`
	Right  []string `toml:"right"`
}

type StatusBarConfig struct {
	Height        int                     `toml:"height"`
	Layout        StatusBarLayout         `toml:"layout"`
	ModuleConfigs map[string]ModuleConfig `toml:"module_configs"`
	Colors        ColorsConfig            `toml:"colors"`
}

type ModuleConfig struct {
	Interval   int                    `toml:"interval"`
	Format     string                 `toml:"format"`
	Enabled    bool                   `toml:"enabled"`
	CSSClasses []string               `toml:"css_classes"`
	Styles     string                 `toml:"styles"`
	Properties map[string]interface{} `toml:"properties"`
}

// ToMap converts ModuleConfig to map[string]interface{} for use with modules
func (c *ModuleConfig) ToMap() map[string]interface{} {
	result := make(map[string]interface{})

	if c.Interval > 0 {
		result["interval"] = fmt.Sprintf("%ds", c.Interval)
	}

	if c.Format != "" {
		result["format"] = c.Format
	}

	result["enabled"] = c.Enabled

	if len(c.CSSClasses) > 0 {
		result["css_classes"] = c.CSSClasses
	}

	if c.Styles != "" {
		result["styles"] = c.Styles
	}

	if len(c.Properties) > 0 {
		for k, v := range c.Properties {
			result[k] = v
		}
	}

	return result
}

type LauncherConfig struct {
	Window      WindowConfig      `toml:"window"`
	Animation   AnimationConfig   `toml:"animation"`
	Search      SearchConfig      `toml:"search"`
	Performance PerformanceConfig `toml:"performance"`
	Icons       IconsConfig       `toml:"icons"`
	Behavior    BehaviorConfig    `toml:"behavior"`
	Keys        KeysConfig        `toml:"keys"`
	DesktopApps DesktopAppsConfig `toml:"desktop_apps"`
	Cache       CacheConfig       `toml:"cache"`
}

type WindowConfig struct {
	Width             int  `toml:"width"`
	Height            int  `toml:"height"`
	Resizable         bool `toml:"resizable"`
	Modal             bool `toml:"modal"`
	Decorated         bool `toml:"decorated"`
	ShowMenubar       bool `toml:"show_menubar"`
	DestroyWithParent bool `toml:"destroy_with_parent"`
	HideOnClose       bool `toml:"hide_on_close"`
}

type AnimationConfig struct {
	EnableSlideIn bool `toml:"enable_slide_in"`
	SlideDuration int  `toml:"slide_duration"` // ms per frame
	SlideStep     int  `toml:"slide_step"`     // pixels per frame
	TargetMargin  int  `toml:"target_margin"`  // margin from top
}

type SearchConfig struct {
	MaxResults        int  `toml:"max_results"`
	MaxCommandResults int  `toml:"max_command_results"`
	DebounceDelay     int  `toml:"debounce_delay"` // milliseconds
	FuzzySearch       bool `toml:"fuzzy_search"`
	CaseSensitive     bool `toml:"case_sensitive"`
	ShowHiddenApps    bool `toml:"show_hidden_apps"`
}

type PerformanceConfig struct {
	EnableCache             bool `toml:"enable_cache"`
	CacheMaxAgeHours        int  `toml:"cache_max_age_hours"`
	SearchCacheSize         int  `toml:"search_cache_size"`
	EnableBackgroundLoading bool `toml:"enable_background_loading"`
	MaxVisibleResults       int  `toml:"max_visible_results"`
}

type IconsConfig struct {
	EnableIcons  bool   `toml:"enable_icons"`
	IconSize     int    `toml:"icon_size"`
	CacheIcons   bool   `toml:"cache_icons"`
	CacheSize    int    `toml:"cache_size"`
	FallbackIcon string `toml:"fallback_icon"`
}

type BehaviorConfig struct {
	ActivateOnHover         bool `toml:"activate_on_hover"`
	ClearSearchOnActivate   bool `toml:"clear_search_on_activate"`
	CloseOnActivate         bool `toml:"close_on_activate"`
	ShowRecentApps          bool `toml:"show_recent_apps"`
	MaxRecentApps           int  `toml:"max_recent_apps"`
	DesktopLauncherFastPath bool `toml:"desktop_launcher_fast_path"`
}

type KeysConfig struct {
	Up          []string `toml:"up"`
	Down        []string `toml:"down"`
	Activate    []string `toml:"activate"`
	Close       []string `toml:"close"`
	TabComplete []string `toml:"tab_complete"`
	QuickSelect []string `toml:"quick_select"`
}

type DesktopAppsConfig struct {
	ScanUserDir    bool     `toml:"scan_user_dir"`
	ScanSystemDirs bool     `toml:"scan_system_dirs"`
	CustomDirs     []string `toml:"custom_dirs"`
	MaxScanTime    float64  `toml:"max_scan_time"` // seconds
}

type CacheConfig struct {
	CacheDir      string `toml:"cache_dir"`
	AppsCacheFile string `toml:"apps_cache_file"`
}

type NotificationConfig struct {
	History  NotificationHistoryConfig  `toml:"history"`
	UI       NotificationUIConfig       `toml:"ui"`
	Daemon   NotificationDaemonConfig   `toml:"daemon"`
	Timeouts NotificationTimeoutsConfig `toml:"timeouts"`
}

type NotificationHistoryConfig struct {
	MaxHistory  int    `toml:"max_history"`
	MaxAgeDays  int    `toml:"max_age_days"`
	PersistPath string `toml:"persist_path"`
}

type NotificationUIConfig struct {
	Icon            string `toml:"icon"`
	ShowUnreadCount bool   `toml:"show_unread_count"`
	MaxDisplay      int    `toml:"max_display"`
	GroupByApp      bool   `toml:"group_by_app"`
	TimestampFormat string `toml:"timestamp_format"`
}

type NotificationDaemonConfig struct {
	Enabled           bool   `toml:"enabled"`
	Position          string `toml:"position"`
	MaxBanners        int    `toml:"max_banners"`
	BannerGap         int    `toml:"banner_gap"`
	BannerWidth       int    `toml:"banner_width"`
	BannerHeight      int    `toml:"banner_height"`
	AnimationDuration int    `toml:"animation_duration"`
}

type NotificationTimeoutsConfig struct {
	Low      int `toml:"low"`
	Normal   int `toml:"normal"`
	Critical int `toml:"critical"`
}

type FileSearchConfig struct {
	SearchPaths []string `toml:"search_paths"`
	Exclusions  []string `toml:"exclusions"`
	MaxResults  int      `toml:"max_results"`
}

type ColorsConfig struct {
	Background string `toml:"background"`
	Foreground string `toml:"foreground"`
	Border     string `toml:"border"`
}

var DefaultConfig = Config{
	AppName:    "locus_bar",
	AppID:      "com.github.sigma.locus",
	SocketPath: "/tmp/locus_socket",
	CacheDir:   "~/.cache/locus",
	ConfigDir:  "~/.config/locus",
	StatusBar: StatusBarConfig{
		Height: 40,
		Layout: StatusBarLayout{
			Left: []string{
				"launcher",
				"workspaces",
				"binding_mode",
				"emacs_clock",
			},
			Middle: []string{},
			Right: []string{
				"notifications",
				"time",
				"battery",
				"custom_message",
			},
		},
		ModuleConfigs: map[string]ModuleConfig{
			"time": {
				Interval: 1,
				Format:   "15:04:05",
				Enabled:  true,
			},
			"battery": {
				Interval: 30,
				Enabled:  true,
			},
			"emacs_clock": {
				Interval: 10,
				Enabled:  true,
			},
		},
		Colors: ColorsConfig{
			Background: "#0e1419",
			Foreground: "#ebdbb2",
			Border:     "#444444",
		},
	},
	Launcher: LauncherConfig{
		Window: WindowConfig{
			Width:             600,
			Height:            400,
			Resizable:         true,
			Modal:             false,
			Decorated:         false,
			ShowMenubar:       false,
			DestroyWithParent: true,
			HideOnClose:       true,
		},
		Animation: AnimationConfig{
			EnableSlideIn: true,
			SlideDuration: 20,
			SlideStep:     100,
			TargetMargin:  40,
		},
		Search: SearchConfig{
			MaxResults:        10, // Reduced for better performance
			MaxCommandResults: 10,
			DebounceDelay:     100, // Faster response
			FuzzySearch:       true,
			CaseSensitive:     false,
			ShowHiddenApps:    false,
		},
		Performance: PerformanceConfig{
			EnableCache:             true,
			CacheMaxAgeHours:        24,  // Longer cache life
			SearchCacheSize:         200, // Larger cache
			EnableBackgroundLoading: true,
			MaxVisibleResults:       10, // Fewer widgets
		},
		Icons: IconsConfig{
			EnableIcons:  true,
			IconSize:     32,
			CacheIcons:   true,
			CacheSize:    500, // Larger icon cache
			FallbackIcon: "image-missing",
		},
		Behavior: BehaviorConfig{
			ActivateOnHover:         false,
			ClearSearchOnActivate:   true,
			CloseOnActivate:         true,
			ShowRecentApps:          false,
			MaxRecentApps:           5,
			DesktopLauncherFastPath: true,
		},
		Keys: KeysConfig{
			Up:          []string{"Up", "Ctrl+P", "Ctrl+K"},
			Down:        []string{"Down", "Ctrl+N", "Ctrl+J"},
			Activate:    []string{"Return", "KP_Enter"},
			Close:       []string{"Escape"},
			TabComplete: []string{"Tab", "Ctrl+L"},
			QuickSelect: []string{"Alt+1", "Alt+2", "Alt+3", "Alt+4", "Alt+5", "Alt+6", "Alt+7", "Alt+8", "Alt+9"},
		},
		DesktopApps: DesktopAppsConfig{
			ScanUserDir:    true,
			ScanSystemDirs: true,
			CustomDirs:     []string{},
			MaxScanTime:    5.0,
		},
		Cache: CacheConfig{
			CacheDir:      "~/.cache/locus",
			AppsCacheFile: "apps.json",
		},
	},
	Notification: NotificationConfig{
		History: NotificationHistoryConfig{
			MaxHistory:  500,
			MaxAgeDays:  30,
			PersistPath: "~/.cache/locus/notifications.json",
		},
		UI: NotificationUIConfig{
			Icon:            "notifications:",
			ShowUnreadCount: true,
			MaxDisplay:      50,
			GroupByApp:      true,
			TimestampFormat: "%H:%M",
		},
		Daemon: NotificationDaemonConfig{
			Enabled:           true,
			Position:          "top-right",
			MaxBanners:        5,
			BannerGap:         10,
			BannerWidth:       400,
			BannerHeight:      100,
			AnimationDuration: 200,
		},
		Timeouts: NotificationTimeoutsConfig{
			Low:      3000,
			Normal:   5000,
			Critical: -1, // -1 means no timeout
		},
	},
	FileSearch: FileSearchConfig{
		SearchPaths: []string{"~"},
		Exclusions: []string{
			".git",
			"node_modules",
			"target",
			"build",
			".cache",
			".cargo",
			"go",
			".config",
		},
		MaxResults: 50,
	},
}

func LoadConfig(path string) (*Config, error) {
	expandedPath := expandPath(path)

	if _, err := os.Stat(expandedPath); os.IsNotExist(err) {
		cfg := DefaultConfig
		return &cfg, nil
	}

	data, err := os.ReadFile(expandedPath)
	if err != nil {
		return nil, err
	}

	var cfg Config
	if err := toml.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}

	cfg.CacheDir = expandPath(cfg.CacheDir)
	cfg.ConfigDir = expandPath(cfg.ConfigDir)
	cfg.SocketPath = expandPath(cfg.SocketPath)
	cfg.Notification.History.PersistPath = expandPath(cfg.Notification.History.PersistPath)

	return &cfg, nil
}

func expandPath(path string) string {
	if len(path) > 0 && path[0] == '~' {
		usr, err := user.Current()
		if err == nil {
			return filepath.Join(usr.HomeDir, path[1:])
		}
	}
	return path
}

func SaveConfig(cfg *Config, path string) error {
	expandedPath := expandPath(path)

	dir := filepath.Dir(expandedPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	data, err := toml.Marshal(cfg)
	if err != nil {
		return err
	}

	return os.WriteFile(expandedPath, data, 0644)
}
