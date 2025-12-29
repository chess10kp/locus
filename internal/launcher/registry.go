package launcher

import (
	"bufio"
	"context"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
	"unicode"

	"github.com/chess10kp/locus/internal/apps"
	"github.com/chess10kp/locus/internal/config"
)

type LauncherUI interface {
	UpdateResults(items []*LauncherItem)
	HandleCommand(command string)
}

type LauncherContext struct {
	Config         *config.Config
	UI             LauncherUI
	ShowLockScreen func() error
	Registry       *LauncherRegistry
}

// LauncherSizeMode represents launcher window size mode
type LauncherSizeMode int

const (
	LauncherSizeModeDefault LauncherSizeMode = iota
	LauncherSizeModeWallpaper
	LauncherSizeModeGrid
	LauncherSizeModeCustom
)

// LauncherItem represents a single result item
type LauncherItem struct {
	Title         string
	Subtitle      string
	Icon          string
	ActionData    ActionData
	Launcher      Launcher
	IsGridItem    bool
	ImagePath     string
	Metadata      map[string]string
	PreviewAction func() error
}

// GridConfig represents configuration for grid view layout
type GridConfig struct {
	Columns          int
	ItemWidth        int
	ItemHeight       int
	Spacing          int
	ShowMetadata     bool
	MetadataPosition string
	AspectRatio      string
}

// MetadataPosition constants
const (
	MetadataPositionBottom  = "bottom"
	MetadataPositionOverlay = "overlay"
	MetadataPositionHidden  = "hidden"
)

// AspectRatio constants
const (
	AspectRatioSquare   = "square"
	AspectRatioOriginal = "original"
	AspectRatioFixed    = "fixed"
)

// CtrlNumberAction is a function that performs an action on a launcher item
type CtrlNumberAction func(item *LauncherItem) error

// LauncherFactory creates launcher instances
type LauncherFactory interface {
	Name() string
	Create(cfg *config.Config) Launcher
}

var (
	launcherFactories = make(map[string]LauncherFactory)
	factoriesMutex    sync.RWMutex
)

// RegisterLauncherFactory registers a launcher factory
//
// Example usage:
//
//	type MyLauncherFactory struct{}
//
//	func (f *MyLauncherFactory) Name() string {
//	    return "mylauncher"
//	}
//
//	func (f *MyLauncherFactory) Create(cfg *config.Config) Launcher {
//	    return NewMyLauncher(cfg)
//	}
//
//	func init() {
//	    RegisterLauncherFactory(&MyLauncherFactory{})
//	}
func RegisterLauncherFactory(factory LauncherFactory) {
	factoriesMutex.Lock()
	defer factoriesMutex.Unlock()
	launcherFactories[factory.Name()] = factory
	log.Printf("Registered launcher factory: %s", factory.Name())
}

// GetLauncherFactories returns all registered launcher factories
func GetLauncherFactories() map[string]LauncherFactory {
	factoriesMutex.RLock()
	defer factoriesMutex.RUnlock()

	// Return a copy to avoid race conditions
	factories := make(map[string]LauncherFactory, len(launcherFactories))
	for name, factory := range launcherFactories {
		factories[name] = factory
	}
	return factories
}

// Launcher is the interface that all launchers must implement
type Launcher interface {
	Name() string
	CommandTriggers() []string
	GetSizeMode() LauncherSizeMode
	Populate(query string, ctx *LauncherContext) []*LauncherItem
	GetHooks() []Hook
	Rebuild(ctx *LauncherContext) error
	Cleanup()
	GetCtrlNumberAction(number int) (CtrlNumberAction, bool)
	GetGridConfig() *GridConfig
}

// LauncherRegistry manages all launchers
type LauncherRegistry struct {
	launchers       map[string]Launcher
	triggerMap      map[string]Launcher
	customPrefix    map[string]string // name -> custom prefix
	config          *config.Config
	ctx             *LauncherContext
	searchCache     *SearchCache
	appsHash        string
	hookRegistry    *HookRegistry
	frecencyTracker *FrecencyTracker
}

// NewLauncherRegistry creates a new launcher registry
func NewLauncherRegistry(cfg *config.Config) *LauncherRegistry {
	cache, err := NewSearchCache(cfg.Launcher.Performance.SearchCacheSize)
	if err != nil {
		log.Printf("Failed to create search cache: %v", err)
		// Continue without cache rather than failing
		cache = nil
	}

	dataDir := cfg.CacheDir
	if dataDir == "" {
		homeDir := os.Getenv("HOME")
		if homeDir != "" {
			dataDir = filepath.Join(homeDir, ".local", "share", "locus")
		} else {
			dataDir = "/tmp/locus"
		}
	}

	frecencyTracker, err := NewFrecencyTracker(dataDir)
	if err != nil {
		log.Printf("Failed to create frecency tracker: %v", err)
		frecencyTracker = nil
	}

	registry := &LauncherRegistry{
		launchers:    make(map[string]Launcher),
		triggerMap:   make(map[string]Launcher),
		customPrefix: make(map[string]string),
		config:       cfg,
		ctx: &LauncherContext{
			Config: cfg,
		},
		searchCache:     cache,
		appsHash:        "",
		hookRegistry:    NewHookRegistry(),
		frecencyTracker: frecencyTracker,
	}

	registry.ctx.Registry = registry
	return registry
}

// Register registers a launcher
func (r *LauncherRegistry) Register(launcher Launcher) error {
	name := launcher.Name()

	if _, exists := r.launchers[name]; exists {
		return fmt.Errorf("launcher '%s' already registered", name)
	}

	r.launchers[name] = launcher

	// Register triggers
	for _, trigger := range launcher.CommandTriggers() {
		r.triggerMap[trigger] = launcher
		log.Printf("Registered trigger: %s -> %s", trigger, name)
	}

	return nil
}

// RegisterWithCustomPrefix registers a launcher with custom prefix
func (r *LauncherRegistry) RegisterWithCustomPrefix(launcher Launcher, prefix string) error {
	name := launcher.Name()

	if err := r.Register(launcher); err != nil {
		return err
	}

	r.customPrefix[name] = prefix
	r.triggerMap[prefix] = launcher

	log.Printf("Registered custom prefix: %s -> %s", prefix, name)

	return nil
}

// Unregister unregisters a launcher
func (r *LauncherRegistry) Unregister(name string) {
	if launcher, exists := r.launchers[name]; exists {
		// Remove triggers
		for _, trigger := range launcher.CommandTriggers() {
			delete(r.triggerMap, trigger)
		}

		// Remove custom prefix
		if prefix, ok := r.customPrefix[name]; ok {
			delete(r.triggerMap, prefix)
			delete(r.customPrefix, name)
		}

		launcher.Cleanup()
		delete(r.launchers, name)

		log.Printf("Unregistered launcher: %s", name)
	}
}

// GetLauncher returns a launcher by trigger
func (r *LauncherRegistry) GetLauncher(trigger string) (Launcher, bool) {
	launcher, exists := r.triggerMap[trigger]
	return launcher, exists
}

// FindLauncherForInput finds a launcher for given input
func (r *LauncherRegistry) FindLauncherForInput(input string) (trigger string, launcher Launcher, query string) {
	// Check for ? prefix (help launcher)
	if strings.HasPrefix(input, "?") {
		launcher, exists := r.GetLauncher("?")
		if exists {
			return "?", launcher, input[1:]
		}
	}

	// Check for % prefix (timer launcher)
	if strings.HasPrefix(input, "%") {
		launcher, exists := r.GetLauncher("%")
		if exists {
			return "%", launcher, input[1:]
		}
	}

	// Check for > prefix
	if strings.HasPrefix(input, ">") {
		parts := strings.SplitN(input[1:], " ", 2)
		if len(parts) > 0 {
			trigger = parts[0]
			if len(parts) > 1 {
				query = parts[1]
			}

			launcher, exists := r.GetLauncher(trigger)
			if exists {
				return trigger, launcher, query
			}
		}
	}

	// Check for colon-style triggers (f:, wp:, etc.)
	if strings.Contains(input, ":") {
		parts := strings.SplitN(input, ":", 2)
		if len(parts) > 1 {
			trigger = parts[0]
			query = strings.TrimSpace(parts[1])

			launcher, exists := r.GetLauncher(trigger)
			if exists {
				return trigger, launcher, query
			}
		}
	}

	// Check for space-style triggers (f , m , etc.)
	if strings.Contains(input, " ") {
		parts := strings.SplitN(input, " ", 2)
		if len(parts) > 0 {
			trigger = parts[0]
			if len(parts) > 1 {
				query = strings.TrimSpace(parts[1])
			}

			launcher, exists := r.GetLauncher(trigger)
			if exists {
				return trigger, launcher, query
			}
		}
	}

	return "", nil, ""
}

// GetAllLaunchers returns all registered launchers
func (r *LauncherRegistry) GetAllLaunchers() []Launcher {
	launchers := make([]Launcher, 0, len(r.launchers))
	for _, launcher := range r.launchers {
		launchers = append(launchers, launcher)
	}
	return launchers
}

// Cleanup cleans up all launchers
func (r *LauncherRegistry) Cleanup() {
	for name, launcher := range r.launchers {
		launcher.Cleanup()
		log.Printf("Cleaned up launcher: %s", name)
	}

	r.launchers = make(map[string]Launcher)
	r.triggerMap = make(map[string]Launcher)
	r.customPrefix = make(map[string]string)

	// Clear search cache
	if r.searchCache != nil {
		r.searchCache.Invalidate()
	}
	r.appsHash = ""
}

// Search searches for items matching the query
func (r *LauncherRegistry) Search(query string) ([]*LauncherItem, error) {
	startTime := time.Now()
	log.Printf("[REGISTRY-SEARCH] Started for query='%s'", query)

	_, l, q := r.FindLauncherForInput(query)

	if l != nil {
		// Launcher-specific search - only search this launcher
		log.Printf("[REGISTRY-SEARCH] Launcher-specific search: launcher='%s', query='%s'", l.Name(), q)
		populateStart := time.Now()
		items := l.Populate(q, r.ctx)
		log.Printf("[REGISTRY-SEARCH] Launcher-specific populate completed in %v, %d items", time.Since(populateStart), len(items))

		// Apply max results limit
		maxResults := r.config.Launcher.Search.MaxResults
		if len(items) > maxResults {
			items = items[:maxResults]
			log.Printf("[REGISTRY-SEARCH] Limited results to %d (max configured)", maxResults)
		}

		// Don't cache launcher-specific searches
		log.Printf("[REGISTRY-SEARCH] Completed launcher-specific search in %v", time.Since(startTime))
		return items, nil
	}

	// General app search - check cache first
	if r.searchCache != nil {
		cacheCheckStart := time.Now()
		if cachedResults, found := r.searchCache.Get(query, r.appsHash); found {
			log.Printf("[REGISTRY-SEARCH] Cache HIT for query='%s', returned %d items in %v", query, len(cachedResults), time.Since(cacheCheckStart))
			// Log cache stats periodically (every 10 hits to avoid spam)
			if atomic.LoadInt64(&r.searchCache.hits)%10 == 0 {
				stats := r.searchCache.GetStats()
				log.Printf("[REGISTRY-SEARCH] Cache stats: hits=%d, misses=%d, hit_rate=%.2f%%", stats.Hits, stats.Misses, stats.HitRate*100)
			}
			return cachedResults, nil
		}
		log.Printf("[REGISTRY-SEARCH] Cache MISS for query='%s' in %v", query, time.Since(cacheCheckStart))
	} else {
		log.Printf("[REGISTRY-SEARCH] No cache available")
	}

	// Find app launcher and search it (only search apps for general queries)
	var items []*LauncherItem
	var appLauncher Launcher

	for _, l := range r.launchers {
		if l.Name() == "apps" {
			appLauncher = l
			break
		}
	}

	if appLauncher != nil {
		log.Printf("[REGISTRY-SEARCH] Using AppLauncher for general query='%s'", query)
		populateStart := time.Now()
		items = appLauncher.Populate(query, r.ctx)
		log.Printf("[REGISTRY-SEARCH] AppLauncher populate completed in %v, %d items", time.Since(populateStart), len(items))
	} else {
		// Fallback: search all launchers (shouldn't happen)
		log.Printf("[REGISTRY-SEARCH] WARNING: No AppLauncher found, falling back to all launchers")
		for _, launcher := range r.launchers {
			launcherItems := launcher.Populate(query, r.ctx)
			items = append(items, launcherItems...)
		}
	}

	// Deduplicate results
	originalCount := len(items)
	items = r.deduplicateResults(items)
	if len(items) != originalCount {
		log.Printf("[REGISTRY-SEARCH] Deduplication removed %d duplicates (%d -> %d)", originalCount-len(items), originalCount, len(items))
	}

	// Apply max results limit
	maxResults := r.config.Launcher.Search.MaxResults
	if len(items) > maxResults {
		items = items[:maxResults]
		log.Printf("[REGISTRY-SEARCH] Limited results to %d (max configured)", maxResults)
	}

	// Cache the results if cache is available
	if r.searchCache != nil {
		durationMs := float64(time.Since(startTime).Nanoseconds()) / 1e6
		r.searchCache.Put(query, r.appsHash, items, durationMs)
		log.Printf("[REGISTRY-SEARCH] Cached results for query='%s' (duration=%.2fms)", query, durationMs)
	}

	log.Printf("[REGISTRY-SEARCH] Completed general search in %v, final result count: %d", time.Since(startTime), len(items))
	return items, nil
}

// deduplicateResults removes duplicate results based on title and subtitle
func (r *LauncherRegistry) deduplicateResults(items []*LauncherItem) []*LauncherItem {
	// Pre-allocate with capacity to reduce allocations
	seen := make(map[string]bool, len(items))
	result := make([]*LauncherItem, 0, len(items))

	for _, item := range items {
		// Use title only as key in most cases - subtitle adds little value
		// This reduces memory usage and improves performance
		key := item.Title
		if item.Subtitle != "" {
			key += "|" + item.Subtitle
		}

		if !seen[key] {
			seen[key] = true
			result = append(result, item)
		}
	}

	return result
}

// UpdateAppsHash updates the apps hash for cache invalidation
func (r *LauncherRegistry) UpdateAppsHash(apps []apps.App) {
	if r.searchCache != nil {
		r.appsHash = ComputeAppsHash(apps)
	}
}

// UpdateAppsHashFromLauncher updates the apps hash from the AppLauncher
func (r *LauncherRegistry) UpdateAppsHashFromLauncher() {
	if r.searchCache != nil {
		for _, launcher := range r.launchers {
			if appLauncher, ok := launcher.(*AppLauncher); ok {
				r.appsHash = appLauncher.GetAppsHash()
				break
			}
		}
	}
}

// GetCacheStats returns current cache statistics
func (r *LauncherRegistry) GetCacheStats() *CacheStats {
	if r.searchCache != nil {
		return r.searchCache.GetStats()
	}
	return nil
}

// Execute executes a launcher item
func (r *LauncherRegistry) Execute(item *LauncherItem) error {
	if r.frecencyTracker != nil && item.Launcher.Name() == "apps" {
		r.frecencyTracker.RecordLaunch(item.Title)
	}

	return r.ExecuteWithActionData(item.Launcher.Name(), item.ActionData)
}

// ExecuteWithActionData executes an action data for a launcher
func (r *LauncherRegistry) ExecuteWithActionData(launcherName string, data ActionData) error {
	if data == nil {
		return fmt.Errorf("no action data provided")
	}

	switch data.Type() {
	case "shell":
		shellAction, ok := data.(*ShellAction)
		if !ok {
			return fmt.Errorf("invalid shell action type")
		}
		return r.executeShellCommand(shellAction.Command)

	case "desktop":
		desktopAction, ok := data.(*DesktopAction)
		if !ok {
			return fmt.Errorf("invalid desktop action type")
		}
		return r.executeDesktopAction(desktopAction.File)

	case "clipboard":
		clipboardAction, ok := data.(*ClipboardAction)
		if !ok {
			return fmt.Errorf("invalid clipboard action type")
		}
		return r.executeClipboardAction(clipboardAction)

	case "notification":
		notificationAction, ok := data.(*NotificationAction)
		if !ok {
			return fmt.Errorf("invalid notification action type")
		}
		return r.executeNotificationAction(notificationAction)

	case "status_message":
		statusAction, ok := data.(*StatusMessageAction)
		if !ok {
			return fmt.Errorf("invalid status message action type")
		}
		return r.executeStatusMessageAction(statusAction)

	case "rebuild_launcher":
		rebuildAction, ok := data.(*RebuildLauncherAction)
		if !ok {
			return fmt.Errorf("invalid rebuild launcher action type")
		}
		return r.executeRebuildLauncherAction(rebuildAction)

	case "window_focus":
		windowAction, ok := data.(*WindowFocusAction)
		if !ok {
			return fmt.Errorf("invalid window focus action type")
		}
		return r.executeWindowFocusAction(windowAction)

	case "color":
		colorAction, ok := data.(*ColorAction)
		if !ok {
			return fmt.Errorf("invalid color action type")
		}
		return r.executeColorAction(colorAction)

	default:
		// Custom action - pass to launcher hooks if available
		ctx := &HookContext{
			LauncherName: launcherName,
			Config:       r.config,
		}
		result := r.hookRegistry.ExecuteSelectHooks(context.Background(), ctx, data)
		if result.Handled {
			return nil
		}

		return fmt.Errorf("unsupported action type: %s", data.Type())
	}
}

// executeShellCommand executes a shell command
func (r *LauncherRegistry) executeShellCommand(command string) error {
	if command == "" {
		return fmt.Errorf("empty command")
	}

	parts, err := r.splitCommand(command)
	if err != nil {
		return fmt.Errorf("failed to parse shell command: %w", err)
	}
	if len(parts) == 0 {
		return fmt.Errorf("empty command")
	}

	cmd := exec.Command(parts[0], parts[1:]...)
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setsid: true,
	}

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start command: %w", err)
	}

	return nil
}

// executeDesktopAction launches a desktop application
func (r *LauncherRegistry) executeDesktopAction(filePath string) error {
	if filePath == "" {
		return fmt.Errorf("empty desktop file path")
	}

	// Parse the desktop file to get the Exec command and Path
	execCmd, workingDir, err := r.parseDesktopFile(filePath)
	if err != nil {
		return fmt.Errorf("failed to parse desktop file: %w", err)
	}

	if execCmd == "" {
		return fmt.Errorf("no Exec command in desktop file")
	}

	// Strip field codes like %f, %u, etc. (similar to Python implementation)
	execCmd = r.stripFieldCodes(execCmd)

	// Split the command with proper quote handling (like Python's shlex.split)
	parts, err := r.splitCommand(execCmd)
	if err != nil {
		return fmt.Errorf("failed to parse command: %w", err)
	}
	if len(parts) == 0 {
		return fmt.Errorf("empty exec command")
	}

	// Use systemd-run if available (like Python implementation)
	var cmd *exec.Cmd
	if r.isSystemdRunAvailable() {
		// systemd-run --user --scope --quiet <command>
		args := append([]string{"--user", "--scope", "--quiet"}, parts...)
		cmd = exec.Command("systemd-run", args...)
	} else {
		cmd = exec.Command(parts[0], parts[1:]...)
		cmd.SysProcAttr = &syscall.SysProcAttr{
			Setsid: true,
		}
	}

	// Sanitize environment (remove LD_PRELOAD like Python)
	cmd.Env = r.sanitizeEnvironment()

	// Set working directory if specified in desktop file
	if workingDir != "" {
		cmd.Dir = workingDir
	}

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start desktop application: %w", err)
	}

	return nil
}

// parseDesktopFile parses the Exec and Path fields from a desktop file
func (r *LauncherRegistry) parseDesktopFile(filePath string) (execCmd string, workingDir string, err error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", "", err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "Exec=") {
			execCmd = strings.TrimPrefix(line, "Exec=")
		} else if strings.HasPrefix(line, "Path=") {
			workingDir = strings.TrimPrefix(line, "Path=")
		}
	}

	if execCmd == "" {
		return "", "", fmt.Errorf("Exec field not found")
	}

	return execCmd, workingDir, nil
}

// stripFieldCodes removes desktop entry field codes like %f, %u, etc.
func (r *LauncherRegistry) stripFieldCodes(cmd string) string {
	// Remove field codes using regex (similar to Python's re.sub)
	re := regexp.MustCompile(`%[uUfFdDnNickvm]`)
	return strings.TrimSpace(re.ReplaceAllString(cmd, ""))
}

// splitCommand splits a command string like shlex.split() in Python
func (r *LauncherRegistry) splitCommand(cmd string) ([]string, error) {
	var parts []string
	var current strings.Builder
	var inQuotes bool
	var escapeNext bool

	for i, char := range cmd {
		switch {
		case escapeNext:
			current.WriteRune(char)
			escapeNext = false
		case char == '\\':
			escapeNext = true
		case char == '"':
			inQuotes = !inQuotes
		case char == '\'' && !inQuotes:
			// Handle single quotes (simple case)
			inQuotes = !inQuotes
		case unicode.IsSpace(char) && !inQuotes:
			if current.Len() > 0 {
				parts = append(parts, current.String())
				current.Reset()
			}
		default:
			current.WriteRune(char)
		}

		// Check for unmatched quotes
		if i == len(cmd)-1 && inQuotes {
			return nil, fmt.Errorf("unmatched quotes in command")
		}
	}

	if current.Len() > 0 {
		parts = append(parts, current.String())
	}

	if escapeNext {
		return nil, fmt.Errorf("incomplete escape sequence")
	}

	return parts, nil
}

// isSystemdRunAvailable checks if systemd-run is available
func (r *LauncherRegistry) isSystemdRunAvailable() bool {
	_, err := exec.LookPath("systemd-run")
	return err == nil
}

// sanitizeEnvironment removes problematic environment variables
func (r *LauncherRegistry) sanitizeEnvironment() []string {
	env := os.Environ()
	var sanitized []string

	for _, e := range env {
		if strings.HasPrefix(e, "LD_PRELOAD=") {
			// Skip LD_PRELOAD (like Python implementation)
			continue
		}
		if strings.HasPrefix(e, "GDK_BACKEND=") {
			// Critical fix for Rider: Only keep GDK_BACKEND if it's exactly "wayland"
			value := strings.TrimPrefix(e, "GDK_BACKEND=")
			if value == "wayland" {
				sanitized = append(sanitized, e)
			}
			continue
		}
		sanitized = append(sanitized, e)
	}

	return sanitized
}

// executeClipboardAction handles clipboard operations
func (r *LauncherRegistry) executeClipboardAction(action *ClipboardAction) error {
	// TODO: Implement clipboard operations
	return fmt.Errorf("clipboard actions not yet implemented")
}

// executeNotificationAction sends a notification
func (r *LauncherRegistry) executeNotificationAction(action *NotificationAction) error {
	// TODO: Implement notification sending
	return fmt.Errorf("notification actions not yet implemented")
}

// executeStatusMessageAction displays a status message
func (r *LauncherRegistry) executeStatusMessageAction(action *StatusMessageAction) error {
	// TODO: Send status message via IPC
	return fmt.Errorf("status message actions not yet implemented")
}

// executeRebuildLauncherAction rebuilds a launcher
func (r *LauncherRegistry) executeRebuildLauncherAction(action *RebuildLauncherAction) error {
	return r.RefreshLauncher(action.LauncherName)
}

// executeWindowFocusAction switches to workspace and focuses a specific window
func (r *LauncherRegistry) executeWindowFocusAction(action *WindowFocusAction) error {
	// Detect WM command
	wmCommand := "swaymsg"
	for _, cmd := range []string{"scrollmsg", "swaymsg", "i3-msg"} {
		if _, err := exec.LookPath(cmd); err == nil {
			wmCommand = cmd
			break
		}
	}

	// First, switch to the workspace
	workspaceCmd := fmt.Sprintf("%s workspace %s", wmCommand, action.Workspace)
	if err := r.executeShellCommand(workspaceCmd); err != nil {
		return fmt.Errorf("failed to switch to workspace: %w", err)
	}

	// Then focus the specific window by container ID
	focusCmd := fmt.Sprintf("%s [con_id=%d] focus", wmCommand, action.ConID)
	return r.executeShellCommand(focusCmd)
}

// executeColorAction handles color picker operations
func (r *LauncherRegistry) executeColorAction(action *ColorAction) error {
	switch action.Action {
	case "save":
		// Save color to statusbar via IPC
		// Send IPC message to update color module in statusbar
		ipcMessage := fmt.Sprintf("color:%s", action.Color)
		cmd := exec.Command("sh", "-c", fmt.Sprintf("echo %s | nc -U %s 2>/dev/null || echo %s > /tmp/locus_statusbar_ipc", ipcMessage, r.config.SocketPath, ipcMessage))
		if err := cmd.Start(); err != nil {
			log.Printf("Failed to send color IPC message: %v", err)
			return fmt.Errorf("failed to send color to statusbar: %w", err)
		}
		return nil
	case "copy":
		// Copy color to clipboard using wl-copy or xclip
		copyCmd := "echo -n " + action.Color + " | wl-copy 2>/dev/null || echo -n " + action.Color + " | xclip -selection clipboard"
		cmd := exec.Command("sh", "-c", copyCmd)
		cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
		if err := cmd.Start(); err != nil {
			return fmt.Errorf("failed to copy color to clipboard: %w", err)
		}
		return nil
	case "preview":
		// Preview color (already handled in launcher UI)
		return nil
	}
	return fmt.Errorf("unknown color action: %s", action.Action)
}

// RefreshLauncher forces a launcher to refresh its items
func (r *LauncherRegistry) RefreshLauncher(name string) error {
	launcher, exists := r.launchers[name]
	if !exists {
		return fmt.Errorf("launcher '%s' not found", name)
	}

	// Call the launcher's Rebuild method if it implements it
	if rebuildable, ok := launcher.(interface{ Rebuild(*LauncherContext) error }); ok {
		return rebuildable.Rebuild(r.ctx)
	}

	return fmt.Errorf("launcher '%s' does not support rebuilding", name)
}

// GetHookRegistry returns the hook registry
func (r *LauncherRegistry) GetHookRegistry() *HookRegistry {
	return r.hookRegistry
}

// SetLockScreenCallback sets the callback to show lock screen and registers the hook
func (r *LauncherRegistry) SetLockScreenCallback(callback func() error) {
	if r.ctx != nil {
		r.ctx.ShowLockScreen = callback
	}
	// Register or update the lock screen hook with the callback
	// Note: Use "lock" as the key since that's the launcher name
	lockHook := NewLockScreenHook(callback)
	r.hookRegistry.Register("lock", lockHook)
}

// GetLockScreenCallback returns the lock screen callback
func (r *LauncherRegistry) GetLockScreenCallback() func() error {
	if r.ctx != nil {
		return r.ctx.ShowLockScreen
	}
	return nil
}

// registerLauncherHooks registers all hooks for a launcher
func (r *LauncherRegistry) registerLauncherHooks(launcher Launcher) {
	hooks := launcher.GetHooks()
	for _, hook := range hooks {
		if err := r.hookRegistry.Register(launcher.Name(), hook); err != nil {
			log.Printf("Failed to register hook for launcher %s: %v", launcher.Name(), err)
		}
	}
}

// LoadBuiltIn loads built-in launchers using factory pattern
func (r *LauncherRegistry) LoadBuiltIn() error {
	// Initialize context if not already done
	if r.ctx == nil {
		r.ctx = &LauncherContext{
			Config:   r.config,
			Registry: r,
		}
	}

	factories := GetLauncherFactories()

	for name, factory := range factories {
		launcher := factory.Create(r.config)

		// Special handling for AppLauncher - set frecency tracker and start background load
		if name == "apps" {
			if appLauncher, ok := launcher.(*AppLauncher); ok {
				if r.frecencyTracker != nil {
					appLauncher.SetFrecencyTracker(r.frecencyTracker)
					log.Printf("[REGISTRY] Frecency tracker set on AppLauncher")
				}
				appLauncher.StartBackgroundLoad()
			}
		}

		if err := r.Register(launcher); err != nil {
			log.Printf("Failed to register launcher %s: %v", name, err)
			continue
		}

		r.registerLauncherHooks(launcher)
	}

	// Register custom prefixes for specific launchers
	if musicLauncher, exists := r.launchers["music"]; exists {
		if err := r.RegisterWithCustomPrefix(musicLauncher, "m"); err != nil {
			log.Printf("Failed to register music launcher with custom prefix: %v", err)
		}
	}

	// Update apps hash after registration
	r.UpdateAppsHashFromLauncher()

	return nil
}
