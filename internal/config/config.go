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
	LockScreen   LockScreenConfig   `toml:"lock_screen"`
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
	Window           WindowConfig      `toml:"window"`
	Animation        AnimationConfig   `toml:"animation"`
	Search           SearchConfig      `toml:"search"`
	Performance      PerformanceConfig `toml:"performance"`
	Icons            IconsConfig       `toml:"icons"`
	Behavior         BehaviorConfig    `toml:"behavior"`
	Keys             KeysConfig        `toml:"keys"`
	DesktopApps      DesktopAppsConfig `toml:"desktop_apps"`
	Cache            CacheConfig       `toml:"cache"`
	Styling          StylingConfig     `toml:"styling"`
	LauncherPrefixes map[string]string `toml:"launcher_prefixes"`
	Wallpaper        WallpaperConfig   `toml:"wallpaper"`
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

type StylingConfig struct {
	BackgroundColor   string `toml:"background_color"`
	ForegroundColor   string `toml:"foreground_color"`
	BorderColor       string `toml:"border_color"`
	AccentColor       string `toml:"accent_color"`
	EntryBackground   string `toml:"entry_background"`
	EntryBorderColor  string `toml:"entry_border_color"`
	EntryFocusColor   string `toml:"entry_focus_color"`
	ListRowBackground string `toml:"list_row_background"`
	ListRowSelected   string `toml:"list_row_selected"`
	ListRowHover      string `toml:"list_row_hover"`
	ButtonBackground  string `toml:"button_background"`
	ButtonHover       string `toml:"button_hover"`
	BorderRadius      int    `toml:"border_radius"`
	BorderWidth       int    `toml:"border_width"`
	FontFamily        string `toml:"font_family"`
	FontSize          int    `toml:"font_size"`
	FontWeight        string `toml:"font_weight"`
}

type WallpaperConfig struct {
	SetterCommand string `toml:"setter_command"`
	PreviewOnNav  bool   `toml:"preview_on_navigation"`
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
	SearchPaths      []string          `toml:"search_paths"`
	Exclusions       []string          `toml:"exclusions"`
	MaxResults       int               `toml:"max_results"`
	FileOpeners      map[string]string `toml:"file_openers"`
	DefaultOpener    string            `toml:"default_opener"`
	OpenerConfigPath string            `toml:"opener_config_path"`
}

type ColorsConfig struct {
	Background string `toml:"background"`
	Foreground string `toml:"foreground"`
	Border     string `toml:"border"`
}

type LockScreenConfig struct {
	Password     string `toml:"password"`
	PasswordHash string `toml:"password_hash"`
	MaxAttempts  int    `toml:"max_attempts"`
	Enabled      bool   `toml:"enabled"`
	CSS          string `toml:"css"`
}

var DefaultConfig = Config{
	AppName:    "locus_bar",
	AppID:      "com.github.chess10kp.locus",
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
				"timer",
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
		Styling: StylingConfig{
			BackgroundColor:   "#0e1419",
			ForegroundColor:   "#ebdbb2",
			BorderColor:       "#313244",
			AccentColor:       "#89b4fa",
			EntryBackground:   "#181825",
			EntryBorderColor:  "#313244",
			EntryFocusColor:   "#89b4fa",
			ListRowBackground: "#0e1419",
			ListRowSelected:   "#89b4fa",
			ListRowHover:      "#504945",
			ButtonBackground:  "#458588",
			ButtonHover:       "#83a598",
			BorderRadius:      8,
			BorderWidth:       1,
			FontFamily:        "Iosevka, monospace",
			FontSize:          16,
			FontWeight:        "bold",
		},
		LauncherPrefixes: map[string]string{
			"timer": "%",
		},
		Wallpaper: WallpaperConfig{
			SetterCommand: "swww img",
			PreviewOnNav:  true,
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
		FileOpeners: map[string]string{
			".pdf":  "evince",
			".png":  "xdg-open",
			".jpg":  "xdg-open",
			".jpeg": "xdg-open",
			".gif":  "xdg-open",
			".svg":  "xdg-open",
			".webp": "xdg-open",
			".mp4":  "xdg-open",
			".mkv":  "xdg-open",
			".avi":  "xdg-open",
			".mov":  "xdg-open",
			".mp3":  "xdg-open",
			".flac": "xdg-open",
			".ogg":  "xdg-open",
			".wav":  "xdg-open",
			".zip":  "xdg-open",
			".tar":  "xdg-open",
			".gz":   "xdg-open",
			".bz2":  "xdg-open",
			".xz":   "xdg-open",
			".txt":  "xdg-open",
			".md":   "xdg-open",
		},
		DefaultOpener:    "xdg-open",
		OpenerConfigPath: "~/.config/locus/file_openers.toml",
	},
	LockScreen: LockScreenConfig{
		Password:     "",
		PasswordHash: "",
		MaxAttempts:  3,
		Enabled:      true,
		CSS: `#lockscreen-window {
			background-color: #0e1419;
		}
		#lockscreen-entry {
			background-color: #1e1e2e;
			color: #ebdbb2;
			border: 4px solid #458588;
			border-radius: 8px;
			padding: 12px;
			font-size: 18px;
			min-width: 300px;
			box-shadow: 0 0 10px #458588;
		}
		#lockscreen-entry:focus {
			border-color: #83a598;
			background-color: #282838;
		}
		#lockscreen-status {
			color: #ebdbb2;
			font-size: 16px;
		}
		#lockscreen-label {
			color: #ebdbb2;
			font-size: 24px;
	}`,
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

func LoadAndValidateConfig(path string) (*Config, error) {
	cfg, err := LoadConfig(path)
	if err != nil {
		return nil, fmt.Errorf("failed to load config: %w", err)
	}
	if err := cfg.Validate(); err != nil {
		return nil, fmt.Errorf("config validation failed: %w", err)
	}
	return cfg, nil
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

func (c *Config) Validate() error {
	if err := c.validateWindow(); err != nil {
		return err
	}
	if err := c.validateSearch(); err != nil {
		return err
	}
	if err := c.validateStatusBar(); err != nil {
		return err
	}
	if err := c.validateNotification(); err != nil {
		return err
	}
	if err := c.validateIcons(); err != nil {
		return err
	}
	if err := c.validatePerformance(); err != nil {
		return err
	}
	if err := c.validateBehavior(); err != nil {
		return err
	}
	if err := c.validateLockScreen(); err != nil {
		return err
	}
	return nil
}

func (c *Config) validateWindow() error {
	w := c.Launcher.Window
	if w.Width < 100 || w.Width > 4000 {
		return fmt.Errorf("invalid window width: %d (must be 100-4000)", w.Width)
	}
	if w.Height < 100 || w.Height > 4000 {
		return fmt.Errorf("invalid window height: %d (must be 100-4000)", w.Height)
	}
	return nil
}

func (c *Config) validateSearch() error {
	s := c.Launcher.Search
	if s.MaxResults < 1 || s.MaxResults > 1000 {
		return fmt.Errorf("invalid max_results: %d (must be 1-1000)", s.MaxResults)
	}
	if s.MaxCommandResults < 1 || s.MaxCommandResults > 1000 {
		return fmt.Errorf("invalid max_command_results: %d (must be 1-1000)", s.MaxCommandResults)
	}
	if s.DebounceDelay < 0 || s.DebounceDelay > 5000 {
		return fmt.Errorf("invalid debounce_delay: %d (must be 0-5000ms)", s.DebounceDelay)
	}
	return nil
}

func (c *Config) validateStatusBar() error {
	if c.StatusBar.Height < 10 || c.StatusBar.Height > 100 {
		return fmt.Errorf("invalid statusbar height: %d (must be 10-100px)", c.StatusBar.Height)
	}
	return nil
}

func (c *Config) validateNotification() error {
	d := c.Notification.Daemon
	if d.MaxBanners < 1 || d.MaxBanners > 20 {
		return fmt.Errorf("invalid max_banners: %d (must be 1-20)", d.MaxBanners)
	}
	if d.BannerGap < 0 || d.BannerGap > 50 {
		return fmt.Errorf("invalid banner_gap: %d (must be 0-50px)", d.BannerGap)
	}
	if d.BannerWidth < 100 || d.BannerWidth > 2000 {
		return fmt.Errorf("invalid banner_width: %d (must be 100-2000)", d.BannerWidth)
	}
	if d.BannerHeight < 50 || d.BannerHeight > 500 {
		return fmt.Errorf("invalid banner_height: %d (must be 50-500)", d.BannerHeight)
	}
	if d.AnimationDuration < 0 || d.AnimationDuration > 2000 {
		return fmt.Errorf("invalid animation_duration: %d (must be 0-2000ms)", d.AnimationDuration)
	}
	if d.Position != "" {
		validPositions := map[string]bool{
			"top-left": true, "top-center": true, "top-right": true,
			"bottom-left": true, "bottom-center": true, "bottom-right": true,
		}
		if !validPositions[d.Position] {
			return fmt.Errorf("invalid daemon position: %s (must be one of: top-left, top-center, top-right, bottom-left, bottom-center, bottom-right)", d.Position)
		}
	}

	h := c.Notification.History
	if h.MaxHistory < 0 || h.MaxHistory > 10000 {
		return fmt.Errorf("invalid max_history: %d (must be 0-10000)", h.MaxHistory)
	}
	if h.MaxAgeDays < 1 || h.MaxAgeDays > 365 {
		return fmt.Errorf("invalid max_age_days: %d (must be 1-365)", h.MaxAgeDays)
	}

	t := c.Notification.Timeouts
	if t.Low < 0 || t.Low > 60000 {
		return fmt.Errorf("invalid low timeout: %d (must be 0-60000ms)", t.Low)
	}
	if t.Normal < 0 || t.Normal > 60000 {
		return fmt.Errorf("invalid normal timeout: %d (must be 0-60000ms)", t.Normal)
	}
	if t.Critical < -1 || t.Critical > 60000 {
		return fmt.Errorf("invalid critical timeout: %d (must be -1 for no timeout, or 0-60000ms)", t.Critical)
	}

	return nil
}

func (c *Config) validateIcons() error {
	i := c.Launcher.Icons
	if i.IconSize < 16 || i.IconSize > 256 {
		return fmt.Errorf("invalid icon_size: %d (must be 16-256)", i.IconSize)
	}
	if i.CacheSize < 10 || i.CacheSize > 10000 {
		return fmt.Errorf("invalid cache_size: %d (must be 10-10000)", i.CacheSize)
	}
	return nil
}

func (c *Config) validatePerformance() error {
	p := c.Launcher.Performance
	if p.CacheMaxAgeHours < 1 || p.CacheMaxAgeHours > 168 {
		return fmt.Errorf("invalid cache_max_age_hours: %d (must be 1-168 hours)", p.CacheMaxAgeHours)
	}
	if p.SearchCacheSize < 10 || p.SearchCacheSize > 10000 {
		return fmt.Errorf("invalid search_cache_size: %d (must be 10-10000)", p.SearchCacheSize)
	}
	if p.MaxVisibleResults < 1 || p.MaxVisibleResults > 100 {
		return fmt.Errorf("invalid max_visible_results: %d (must be 1-100)", p.MaxVisibleResults)
	}
	return nil
}

func (c *Config) validateBehavior() error {
	b := c.Launcher.Behavior
	if b.MaxRecentApps < 0 || b.MaxRecentApps > 50 {
		return fmt.Errorf("invalid max_recent_apps: %d (must be 0-50)", b.MaxRecentApps)
	}
	if b.DesktopLauncherFastPath && b.MaxRecentApps == 0 {
		return fmt.Errorf("desktop_launcher_fast_path requires max_recent_apps > 0")
	}
	return nil
}

func (c *Config) validateLockScreen() error {
	ls := c.LockScreen
	if ls.MaxAttempts < 1 || ls.MaxAttempts > 10 {
		return fmt.Errorf("invalid max_attempts: %d (must be 1-10)", ls.MaxAttempts)
	}
	if ls.Enabled && ls.Password == "" && ls.PasswordHash == "" {
		return fmt.Errorf("lockscreen enabled but no password or password_hash provided")
	}
	return nil
}

func ValidateConfig(path string) error {
	cfg, err := LoadConfig(path)
	if err != nil {
		return fmt.Errorf("failed to load config: %w", err)
	}
	if err := cfg.Validate(); err != nil {
		return fmt.Errorf("config validation failed: %w", err)
	}
	return nil
}
