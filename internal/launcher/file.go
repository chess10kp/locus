package launcher

import (
	"os"
	"path/filepath"
	"strings"

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
			items = append(items, &LauncherItem{
				Title:    filepath.Base(path),
				Subtitle: path,
				Icon:     "folder",
				Command:  "xdg-open " + path,
			})
		}

		return items
	}

	var lastResults []*LauncherItem

	if q != "" {
		q = strings.ToLower(q)

		homeDir, _ := os.UserHomeDir()

		cmd := exec.Command("find", homeDir)
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

			absPath, _ := filepath.Abs(line)

			items = append(items, &LauncherItem{
				Title:    filepath.Base(absPath),
				Subtitle: absPath,
				Icon:     l.getFileIcon(filepath.Base(line)),
				Command:  "xdg-open " + absPath,
			})
		}

		if len(items) > 50 {
			items = items[:50]
		}

		return items
	}

	return items
}

func (l *FileLauncher) getFileIcon(filename string) string {
	ext := strings.ToLower(filepath.Ext(filename))

	switch ext {
	case ".png", ".jpg", ".jpeg", ".gif", ".svg":
		return "image-x-generic"
	case ".pdf":
		return "application-pdf"
	case ".zip", ".tar", ".gz", ".bz2", ".xz":
		return "application-x-archive"
	case ".mp3", ".mp4", ".flac", ".ogg", ".wav":
		return "audio-x-generic"
	case ".mp4", ".mkv", ".avi", ".mov":
		return "video-x-generic"
	case ".txt", ".md", ".py", ".go", ".rs", ".js":
		return "text-x-generic"
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

	cmd := exec.Command("xdg-open", q)
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
