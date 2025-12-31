package launcher

import (
	"bufio"
	"fmt"
	"log"
	"os"
	"os/exec"
	"strings"
	"sync"

	"github.com/chess10kp/locus/internal/config"
)

type BookmarkLauncher struct {
	config    *config.Config
	bookmarks []string
	mu        sync.RWMutex
}

type BookmarkLauncherFactory struct{}

func (f *BookmarkLauncherFactory) Name() string {
	return "bookmarks"
}

func (f *BookmarkLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewBookmarkLauncher(cfg)
}

func init() {
	RegisterLauncherFactory(&BookmarkLauncherFactory{})
}

func NewBookmarkLauncher(cfg *config.Config) *BookmarkLauncher {
	return &BookmarkLauncher{
		config: cfg,
	}
}

func (l *BookmarkLauncher) Name() string {
	return "bookmarks"
}

func (l *BookmarkLauncher) CommandTriggers() []string {
	return []string{"b"}
}

func (l *BookmarkLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *BookmarkLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *BookmarkLauncher) loadBookmarks() []string {
	bookmarkPath := l.config.Bookmarks.Path
	if bookmarkPath == "" {
		bookmarkPath = "~/.bookmarks"
	}

	homeDir := os.Getenv("HOME")
	if homeDir != "" && strings.HasPrefix(bookmarkPath, "~") {
		bookmarkPath = homeDir + bookmarkPath[1:]
	}

	file, err := os.Open(bookmarkPath)
	if err != nil {
		log.Printf("[BOOKMARK-LAUNCHER] Failed to open bookmarks file: %v", err)
		return []string{}
	}
	defer file.Close()

	var bookmarks []string
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		url := strings.TrimSpace(scanner.Text())
		if url != "" && !strings.HasPrefix(url, "#") {
			bookmarks = append(bookmarks, url)
		}
	}

	if err := scanner.Err(); err != nil {
		log.Printf("[BOOKMARK-LAUNCHER] Error reading bookmarks: %v", err)
	}

	return bookmarks
}

func (l *BookmarkLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	l.mu.Lock()
	if l.bookmarks == nil {
		l.bookmarks = l.loadBookmarks()
	}
	l.mu.Unlock()

	query = strings.TrimSpace(query)

	var items []*LauncherItem

	for _, url := range l.bookmarks {
		if query != "" && !strings.Contains(strings.ToLower(url), strings.ToLower(query)) {
			continue
		}

		items = append(items, &LauncherItem{
			Title:      url,
			Subtitle:   "Open in browser",
			Icon:       "web-browser",
			ActionData: NewShellAction(l.getBrowserCommand() + " " + url),
			Launcher:   l,
		})
	}

	return items
}

func (l *BookmarkLauncher) getBrowserCommand() string {
	cmd := l.config.Bookmarks.BrowserCommand
	if cmd == "" {
		cmd = "xdg-open"
	}
	return cmd
}

func (l *BookmarkLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *BookmarkLauncher) Rebuild(ctx *LauncherContext) error {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.bookmarks = l.loadBookmarks()
	return nil
}

func (l *BookmarkLauncher) Cleanup() {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.bookmarks = nil
}

func (l *BookmarkLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return func(item *LauncherItem) error {
		url := item.Title
		if url == "" {
			return fmt.Errorf("no URL to copy")
		}

		copyCmd := fmt.Sprintf("echo -n %s | wl-copy 2>/dev/null || echo -n %s | xclip -selection clipboard", url, url)
		cmd := exec.Command("sh", "-c", copyCmd)
		if err := cmd.Start(); err != nil {
			return fmt.Errorf("failed to copy to clipboard: %w", err)
		}

		log.Printf("[BOOKMARK-LAUNCHER] Copied to clipboard: %s", url)
		return nil
	}, true
}
