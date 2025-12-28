package launcher

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/chess10kp/locus/internal/config"
)

type FileLauncher struct {
	config       *config.Config
	openerConfig *FileOpenerConfig
}

type FileOpenerConfig struct {
	FileOpeners   map[string]string `toml:"file_openers"`
	DefaultOpener string            `toml:"default_opener"`
}

type FileLauncherFactory struct{}

func (f *FileLauncherFactory) Name() string {
	return "file"
}

func (f *FileLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewFileLauncher(cfg)
}

func init() {
	RegisterLauncherFactory(&FileLauncherFactory{})
}

func NewFileLauncher(cfg *config.Config) *FileLauncher {
	return &FileLauncher{
		config: cfg,
	}
}

func (l *FileLauncher) Name() string {
	return "file"
}

func (l *FileLauncher) CommandTriggers() []string {
	return []string{"file", "f"}
}

func (l *FileLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *FileLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *FileLauncher) Populate(query string, launcherCtx *LauncherContext) []*LauncherItem {
	q := strings.TrimSpace(query)

	if q == "" || len(q) < 3 {
		homeDir, _ := os.UserHomeDir()
		searchPaths := []string{
			filepath.Join(homeDir, "Documents"),
			filepath.Join(homeDir, "Downloads"),
			filepath.Join(homeDir, "Desktop"),
			filepath.Join(homeDir, "Pictures"),
			filepath.Join(homeDir, "Music"),
			filepath.Join(homeDir, "Videos"),
		}

		items := make([]*LauncherItem, 0, len(searchPaths)+1)

		configPath := l.config.FileSearch.OpenerConfigPath
		items = append(items, &LauncherItem{
			Title:      "Configure File Openers",
			Subtitle:   "Edit file type associations",
			Icon:       "preferences-desktop",
			ActionData: NewShellAction(l.getEditorCommand(configPath)),
			Launcher:   l,
		})

		for _, path := range searchPaths {
			if _, err := os.Stat(path); err == nil {
				items = append(items, &LauncherItem{
					Title:      filepath.Base(path),
					Subtitle:   path,
					Icon:       "folder",
					ActionData: NewShellAction("xdg-open " + path),
					Launcher:   l,
				})
			}
		}

		return items
	}

	q = strings.ToLower(q)
	homeDir, _ := os.UserHomeDir()

	// Execute find command with timeout to prevent hanging
	cmdCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	cmd := exec.CommandContext(cmdCtx, "find", homeDir, "-iname", "*"+q+"*", "-type", "f", "-size", "-100M", "-maxdepth", "4")
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	output, err := cmd.CombinedOutput()

	if cmdCtx.Err() == context.DeadlineExceeded {
		return []*LauncherItem{
			{
				Title:      "Search Timeout",
				Subtitle:   "File search took too long",
				Icon:       "dialog-warning",
				ActionData: NewShellAction(""),
				Launcher:   l,
			},
		}
	}

	if err != nil {
		return []*LauncherItem{
			{
				Title:      "Search Error",
				Subtitle:   err.Error(),
				Icon:       "dialog-error",
				ActionData: NewShellAction(""),
				Launcher:   l,
			},
		}
	}

	lines := strings.Split(string(output), "\n")
	items := make([]*LauncherItem, 0)
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		absPath := line
		filename := filepath.Base(absPath)
		opener := l.getFileOpener(absPath)

		items = append(items, &LauncherItem{
			Title:      filename,
			Subtitle:   fmt.Sprintf("Open with %s", opener),
			Icon:       l.getFileIcon(filename),
			ActionData: NewShellAction(fmt.Sprintf("%s %s", opener, absPath)),
			Launcher:   l,
		})

		if len(items) >= 50 {
			break
		}
	}

	return items
}

func (l *FileLauncher) getFileIcon(filename string) string {
	ext := strings.ToLower(filepath.Ext(filename))
	switch ext {
	case ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp":
		return "image-x-generic"
	case ".pdf":
		return "application-pdf"
	case ".zip", ".tar", ".gz", ".bz2", ".xz":
		return "application-x-archive"
	case ".mp3", ".mp4", ".flac", ".ogg", ".wav":
		return "audio-x-generic"
	case ".mkv", ".avi", ".mov":
		return "video-x-generic"
	default:
		return "text-x-generic"
	}
}

func (l *FileLauncher) getEditorCommand(path string) string {
	expandedPath := l.expandPath(path)
	if err := l.ensureConfigExists(expandedPath); err != nil {
		return fmt.Sprintf("xdg-open %s", expandedPath)
	}

	editors := []string{"code", "nvim", "vim", "nano"}
	for _, editor := range editors {
		if _, err := exec.LookPath(editor); err == nil {
			return fmt.Sprintf("%s %s", editor, expandedPath)
		}
	}

	return fmt.Sprintf("xdg-open %s", expandedPath)
}

func (l *FileLauncher) expandPath(path string) string {
	if strings.HasPrefix(path, "~") {
		if homeDir, err := os.UserHomeDir(); err == nil {
			return filepath.Join(homeDir, path[1:])
		}
	}
	return path
}

func (l *FileLauncher) ensureConfigExists(path string) error {
	if _, err := os.Stat(path); err == nil {
		return nil
	}

	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create config directory: %w", err)
	}

	defaultContent := `# File Opener Configuration
# Configure which applications to use for opening different file types
# 
# Format: file_extension = "command"
# Example: ".pdf" = "evince" will open PDFs with evince
#
# Use "default" as fallback for unmatched file types

# Document types
".pdf" = "evince"
".doc" = "libreoffice"
".docx" = "libreoffice"
".odt" = "libreoffice"
".txt" = "xdg-open"
".md" = "xdg-open"

# Image types
".png" = "xdg-open"
".jpg" = "xdg-open"
".jpeg" = "xdg-open"
".gif" = "xdg-open"
".svg" = "xdg-open"
".webp" = "xdg-open"
".bmp" = "xdg-open"

# Video types
".mp4" = "xdg-open"
".mkv" = "xdg-open"
".avi" = "xdg-open"
".mov" = "xdg-open"
".webm" = "xdg-open"
".flv" = "xdg-open"

# Audio types
".mp3" = "xdg-open"
".flac" = "xdg-open"
".ogg" = "xdg-open"
".wav" = "xdg-open"
".m4a" = "xdg-open"

# Archive types
".zip" = "xdg-open"
".tar" = "xdg-open"
".gz" = "xdg-open"
".bz2" = "xdg-open"
".xz" = "xdg-open"
".7z" = "xdg-open"
".rar" = "xdg-open"

# Code files
".py" = "xdg-open"
".go" = "xdg-open"
".rs" = "xdg-open"
".js" = "xdg-open"
".ts" = "xdg-open"
".html" = "xdg-open"
".css" = "xdg-open"
".json" = "xdg-open"
".yaml" = "xdg-open"
".yml" = "xdg-open"
".toml" = "xdg-open"

# Default fallback for any file type not listed above
default = "xdg-open"
`

	return os.WriteFile(path, []byte(defaultContent), 0644)
}

func (l *FileLauncher) loadOpenerConfig() error {
	if l.openerConfig != nil {
		return nil
	}

	configPath := l.expandPath(l.config.FileSearch.OpenerConfigPath)

	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		if err := l.ensureConfigExists(configPath); err != nil {
			return fmt.Errorf("failed to create opener config: %w", err)
		}
	}

	return nil
}

func (l *FileLauncher) getFileOpener(filePath string) string {
	ext := strings.ToLower(filepath.Ext(filePath))

	if opener, ok := l.config.FileSearch.FileOpeners[ext]; ok && opener != "" {
		return opener
	}

	return l.config.FileSearch.DefaultOpener
}

func (l *FileLauncher) openFile(filePath string) error {
	opener := l.getFileOpener(filePath)
	if opener == "" {
		opener = "xdg-open"
	}

	cmd := exec.Command(opener, filePath)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	return cmd.Start()
}

func (l *FileLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *FileLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *FileLauncher) Cleanup() {
}

func (l *FileLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	if number == 1 {
		return func(item *LauncherItem) error {
			configPath := l.config.FileSearch.OpenerConfigPath
			cmd := exec.Command("sh", "-c", l.getEditorCommand(configPath))
			cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
			return cmd.Start()
		}, true
	}
	return nil, false
}
