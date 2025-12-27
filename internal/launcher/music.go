package launcher

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"

	"github.com/sigma/locus-go/internal/config"
)

type MusicLauncher struct {
	config     *config.Config
	musicDir   string
	filesCache []map[string]string
	scanning   bool
	scanned    bool
	mu         sync.RWMutex
}

func NewMusicLauncher(cfg *config.Config) *MusicLauncher {
	musicDir := os.Getenv("MUSIC_DIR")
	if musicDir == "" {
		musicDir = filepath.Join(os.Getenv("HOME"), "Music")
	}

	return &MusicLauncher{
		config:   cfg,
		musicDir: musicDir,
	}
}

func (l *MusicLauncher) Name() string {
	return "music"
}

func (l *MusicLauncher) CommandTriggers() []string {
	return []string{"music", "m"}
}

func (l *MusicLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *MusicLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	// Ensure we have scanned the music directory
	l.mu.Lock()
	if !l.scanned {
		l.scanned = true
		go l.scanMusicDirectory()
	}
	l.mu.Unlock()

	items := []*LauncherItem{}

	// Add control buttons
	status := l.getStatus()
	l.addControls(&items, status, query)

	q := strings.TrimSpace(query)

	// Check if this is a queue view
	if strings.HasPrefix(strings.ToLower(q), "queue") {
		remainingQuery := strings.TrimSpace(strings.TrimPrefix(q, "queue"))
		l.populateQueue(&items, remainingQuery)
	} else {
		// Library view
		l.populateLibrary(&items, q)
	}

	return items
}

func (l *MusicLauncher) addControls(items *[]*LauncherItem, status map[string]string, query string) {
	lowerQuery := strings.ToLower(query)

	stateIcon := "⏹" // stopped
	if status["state"] == "playing" {
		stateIcon = "⏵"
	} else if status["state"] == "paused" {
		stateIcon = "⏸"
	}

	header := fmt.Sprintf("%s %s", stateIcon, status["song"])
	if header == fmt.Sprintf("%s ", stateIcon) {
		header = fmt.Sprintf("%s Stopped", stateIcon)
	}

	// Add control item if query matches or is empty
	if query == "" || strings.Contains(strings.ToLower(header), lowerQuery) ||
		strings.Contains(strings.ToLower(status["volume"]), lowerQuery) {
		*items = append(*items, &LauncherItem{
			Title:      header,
			Subtitle:   fmt.Sprintf("Volume: %s", status["volume"]),
			Icon:       "media-playback-start",
			ActionData: NewMusicAction("toggle", ""),
			Launcher:   l,
		})
	}

	// Add other control buttons
	controls := []struct {
		title, subtitle, action, icon string
	}{
		{"Next Track", "Skip to next song", "next", "media-skip-forward"},
		{"Previous Track", "Go to previous song", "prev", "media-skip-backward"},
		{"Clear Queue", "Clear all songs from queue", "clear", "edit-clear-all"},
		{"View Queue", "Show current playlist", "view_queue", "view-list"},
		{"View Library", "Browse music library", "view_library", "folder-music"},
	}

	for _, ctrl := range controls {
		// Only show control if query matches or is empty
		if query == "" || strings.Contains(strings.ToLower(ctrl.title), lowerQuery) ||
			strings.Contains(strings.ToLower(ctrl.subtitle), lowerQuery) {
			*items = append(*items, &LauncherItem{
				Title:      ctrl.title,
				Subtitle:   ctrl.subtitle,
				Icon:       ctrl.icon,
				ActionData: NewMusicAction(ctrl.action, ""),
				Launcher:   l,
			})
		}
	}
}

func (l *MusicLauncher) populateQueue(items *[]*LauncherItem, query string) {
	output := l.runMPC([]string{"playlist", "-f", "%position%\t%file%"})
	lines := strings.Split(strings.TrimSpace(output), "\n")

	if len(lines) == 0 || (len(lines) == 1 && lines[0] == "") {
		*items = append(*items, &LauncherItem{
			Title:    "Queue is empty",
			Subtitle: "Add some music to get started",
			Icon:     "dialog-information",
			Launcher: l,
		})
		return
	}

	index := 1
	for _, line := range lines {
		if line == "" {
			continue
		}

		parts := strings.SplitN(line, "\t", 2)
		if len(parts) != 2 {
			continue
		}

		pos, filename := parts[0], parts[1]

		// Clean up filename for display
		displayName := filepath.Base(filename)
		if ext := filepath.Ext(displayName); ext != "" {
			displayName = displayName[:len(displayName)-len(ext)]
		}

		// Filter by query if provided
		if query != "" && !strings.Contains(strings.ToLower(displayName), strings.ToLower(query)) {
			continue
		}

		*items = append(*items, &LauncherItem{
			Title:      fmt.Sprintf("%s. %s", pos, displayName),
			Subtitle:   "Click to play this song",
			Icon:       "audio-x-generic",
			ActionData: NewMusicAction("play_position", pos),
			Launcher:   l,
		})

		index++
		if index > 50 { // Limit results
			break
		}
	}
}

func (l *MusicLauncher) populateLibrary(items *[]*LauncherItem, query string) {
	l.mu.RLock()
	files := make([]map[string]string, len(l.filesCache))
	copy(files, l.filesCache)
	scanning := l.scanning
	l.mu.RUnlock()

	if scanning && len(files) == 0 {
		*items = append(*items, &LauncherItem{
			Title:    "Scanning music library...",
			Subtitle: "Please wait while we scan your music",
			Icon:     "view-refresh",
			Launcher: l,
		})
		return
	}

	if len(files) == 0 {
		*items = append(*items, &LauncherItem{
			Title:    "No music files found",
			Subtitle: fmt.Sprintf("Check %s directory", l.musicDir),
			Icon:     "dialog-error",
			Launcher: l,
		})
		return
	}

	index := 1
	for _, item := range files {
		name := item["name"]
		path := item["path"]

		// Filter by query
		if query != "" && !strings.Contains(strings.ToLower(name), strings.ToLower(query)) {
			continue
		}

		*items = append(*items, &LauncherItem{
			Title:      name,
			Subtitle:   path,
			Icon:       "audio-x-generic",
			ActionData: NewMusicAction("play_file", path),
			Launcher:   l,
		})

		index++
		if index > 50 { // Limit results for performance
			break
		}
	}

	if len(*items) == 0 && query != "" {
		*items = append(*items, &LauncherItem{
			Title:    fmt.Sprintf("No matches for '%s'", query),
			Subtitle: "Try a different search term",
			Icon:     "edit-find",
			Launcher: l,
		})
	}
}

func (l *MusicLauncher) scanMusicDirectory() {
	l.mu.Lock()
	l.scanning = true
	l.mu.Unlock()

	defer func() {
		l.mu.Lock()
		l.scanning = false
		l.mu.Unlock()
	}()

	exts := []string{".mp3", ".flac", ".opus", ".ogg", ".m4a", ".wav"}
	var files []map[string]string

	err := filepath.Walk(l.musicDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil // Skip errors
		}

		if !info.IsDir() {
			ext := strings.ToLower(filepath.Ext(path))
			for _, allowedExt := range exts {
				if ext == allowedExt {
					relPath, _ := filepath.Rel(l.musicDir, path)
					files = append(files, map[string]string{
						"name": filepath.Base(path),
						"path": relPath,
					})
					break
				}
			}
		}
		return nil
	})

	if err == nil {
		l.mu.Lock()
		l.filesCache = files
		l.mu.Unlock()
	}
}

func (l *MusicLauncher) getStatus() map[string]string {
	output, err := exec.Command("mpc", "status").Output()
	if err != nil {
		return map[string]string{
			"state":  "stopped",
			"song":   "MPD not running",
			"volume": "",
		}
	}

	status := map[string]string{
		"state":  "stopped",
		"song":   "",
		"volume": "",
	}

	lines := strings.Split(strings.TrimSpace(string(output)), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if strings.Contains(line, "[playing]") {
			status["state"] = "playing"
		} else if strings.Contains(line, "[paused]") {
			status["state"] = "paused"
		} else if strings.HasPrefix(line, "volume:") {
			// Parse volume and other flags
			parts := strings.Split(line, "   ")
			for _, part := range parts {
				if strings.Contains(part, ":") {
					kv := strings.SplitN(part, ":", 2)
					if len(kv) == 2 {
						status[strings.TrimSpace(kv[0])] = strings.TrimSpace(kv[1])
					}
				}
			}
		} else if !strings.Contains(line, "[") && !strings.Contains(line, "volume:") && line != "" {
			// This is the song name
			status["song"] = line
		}
	}

	return status
}

func (l *MusicLauncher) runMPC(args []string) string {
	cmd := exec.Command("mpc", args...)
	output, err := cmd.Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(output))
}

func (l *MusicLauncher) GetHooks() []Hook {
	return []Hook{
		NewMusicHook(l),
	}
}

func (l *MusicLauncher) Rebuild(ctx *LauncherContext) error {
	// Trigger rescan
	go l.scanMusicDirectory()
	return nil
}

func (l *MusicLauncher) Cleanup() {
}

func (l *MusicLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}

// MusicHook handles music-specific actions
type MusicHook struct {
	launcher *MusicLauncher
}

func NewMusicHook(launcher *MusicLauncher) *MusicHook {
	return &MusicHook{launcher: launcher}
}

func (h *MusicHook) ID() string {
	return "music_hook"
}

func (h *MusicHook) Priority() int {
	return 100
}

func (h *MusicHook) OnSelect(execCtx context.Context, ctx *HookContext, data ActionData) HookResult {
	if musicAction, ok := data.(*MusicAction); ok {
		switch musicAction.Action {
		case "play_file":
			h.launcher.playFile(musicAction.Value)
			return HookResult{Handled: true}
		case "play_position":
			h.launcher.playPosition(musicAction.Value)
			return HookResult{Handled: true}
		case "toggle", "next", "prev", "clear":
			h.launcher.control(musicAction.Action)
			return HookResult{Handled: true}
		case "view_queue":
			// This will be handled by setting search text to "m: queue"
			return HookResult{Handled: false}
		case "view_library":
			// This will be handled by setting search text to "m:"
			return HookResult{Handled: false}
		}
	}
	return HookResult{Handled: false}
}

func (h *MusicHook) OnEnter(execCtx context.Context, ctx *HookContext, text string) HookResult {
	// Handle direct commands like ">music clear", ">music next", etc.
	if strings.HasPrefix(text, ">music") || strings.HasPrefix(text, ">m") {
		cmd := strings.TrimSpace(strings.TrimPrefix(strings.TrimPrefix(text, ">music"), ">m"))
		if cmd == "" {
			// Refresh music library view
			return HookResult{Handled: true}
		}

		switch cmd {
		case "clear", "pause", "play", "next", "prev":
			h.launcher.control(cmd)
			return HookResult{Handled: true}
		case "queue":
			// This will be handled by the populate method
			return HookResult{Handled: true}
		}
	}
	return HookResult{Handled: false}
}

func (h *MusicHook) OnTab(execCtx context.Context, ctx *HookContext, text string) TabResult {
	return TabResult{Handled: false}
}

func (h *MusicHook) Cleanup() {
}

// Helper methods for music actions
func (l *MusicLauncher) playFile(relPath string) {
	l.runMPC([]string{"add", relPath})
	status := l.getStatus()
	if status["state"] != "playing" {
		l.runMPC([]string{"play"})
	}
}

func (l *MusicLauncher) playPosition(pos string) {
	l.runMPC([]string{"play", pos})
}

func (l *MusicLauncher) control(command string) {
	switch command {
	case "toggle":
		l.runMPC([]string{"toggle"})
	case "play":
		l.runMPC([]string{"play"})
	case "pause":
		l.runMPC([]string{"pause"})
	case "next":
		l.runMPC([]string{"next"})
	case "prev":
		l.runMPC([]string{"prev"})
	case "clear":
		l.runMPC([]string{"clear"})
	}
}
