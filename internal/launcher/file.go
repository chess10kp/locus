package launcher

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"

	"github.com/sigma/locus-go/internal/config"
)

type FileLauncher struct {
	config *config.Config
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

func (l *FileLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	q := strings.TrimSpace(query)

	if q == "" {
		homeDir, _ := os.UserHomeDir()
		searchPaths := []string{
			filepath.Join(homeDir, "Documents"),
			filepath.Join(homeDir, "Downloads"),
			filepath.Join(homeDir, "Desktop"),
			filepath.Join(homeDir, "Pictures"),
			filepath.Join(homeDir, "Music"),
			filepath.Join(homeDir, "Videos"),
		}

		items := make([]*LauncherItem, 0, len(searchPaths))
		for _, path := range searchPaths {
			if _, err := os.Stat(path); err == nil {
				items = append(items, &LauncherItem{
					Title:    filepath.Base(path),
					Subtitle: path,
					Icon:     "folder",
					Command:  "xdg-open " + path,
				})
			}
		}

		return items
	}

	q = strings.ToLower(q)
	homeDir, _ := os.UserHomeDir()

	cmd := exec.Command("find", homeDir, "-iname", "*"+q+"*", "-type", "f", "-size", "-100M")
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	output, err := cmd.CombinedOutput()
	if err != nil {
		return []*LauncherItem{
			{
				Title:    "Search Error",
				Subtitle: err.Error(),
				Icon:     "dialog-error",
				Command:  "",
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

		items = append(items, &LauncherItem{
			Title:    filename,
			Subtitle: absPath,
			Icon:     l.getFileIcon(filename),
			Command:  "xdg-open " + absPath,
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

func (l *FileLauncher) HandlesEnter() bool {
	return true
}

func (l *FileLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	q := strings.TrimSpace(query)
	if q == "" {
		return false
	}

	absPath, err := filepath.Abs(q)
	if err != nil {
		return false
	}

	cmd := exec.Command("xdg-open", absPath)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	return cmd.Start() == nil
}

func (l *FileLauncher) HandlesTab() bool {
	return false
}

func (l *FileLauncher) HandleTab(query string) string {
	return query
}

func (l *FileLauncher) Cleanup() {
}
