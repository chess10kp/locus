package launcher

import (
	"fmt"
	"os/exec"
	"strings"
	"syscall"

	"github.com/sigma/locus-go/internal/config"
)

type ShellLauncher struct {
	config *config.Config
}

func NewShellLauncher() *ShellLauncher {
	return &ShellLauncher{}
}

func (l *ShellLauncher) Name() string {
	return "shell"
}

func (l *ShellLauncher) CommandTriggers() []string {
	return []string{">", "sh", "shell", "cmd", "command"}
}

func (l *ShellLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *ShellLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	if strings.TrimSpace(query) == "" {
		return nil
	}

	return []*LauncherItem{
		{
			Title:    fmt.Sprintf("Run: %s", query),
			Subtitle: "Execute in shell",
			Icon:     "utilities-terminal",
			Command:  query,
			Launcher: l,
		},
	}
}

func (l *ShellLauncher) HandlesEnter() bool {
	return true
}

func (l *ShellLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	if strings.TrimSpace(query) == "" {
		return false
	}

	parts := strings.Fields(query)
	cmd := exec.Command(parts[0], parts[1:]...)
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setsid: true,
	}

	if err := cmd.Start(); err != nil {
		fmt.Printf("Failed to start command: %v\n", err)
		return false
	}

	return true
}

func (l *ShellLauncher) HandlesTab() bool {
	return false
}

func (l *ShellLauncher) HandleTab(query string) string {
	return query
}

func (l *ShellLauncher) Cleanup() {
}

type WebLauncher struct {
	config *config.Config
}

func NewWebLauncher() *WebLauncher {
	return &WebLauncher{}
}

func (l *WebLauncher) Name() string {
	return "web"
}

func (l *WebLauncher) CommandTriggers() []string {
	return []string{":", "web", "url", "open"}
}

func (l *WebLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *WebLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	if strings.TrimSpace(query) == "" {
		return nil
	}

	url := query
	if !strings.HasPrefix(strings.ToLower(query), "http://") &&
		!strings.HasPrefix(strings.ToLower(query), "https://") {
		url = "https://" + query
	}

	return []*LauncherItem{
		{
			Title:    fmt.Sprintf("Open: %s", query),
			Subtitle: url,
			Icon:     "web-browser",
			Command:  fmt.Sprintf("xdg-open %s", url),
			Launcher: l,
		},
	}
}

func (l *WebLauncher) HandlesEnter() bool {
	return true
}

func (l *WebLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	url := query
	if !strings.HasPrefix(strings.ToLower(query), "http://") &&
		!strings.HasPrefix(strings.ToLower(query), "https://") {
		url = "https://" + query
	}

	cmd := exec.Command("xdg-open", url)
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setsid: true,
	}

	if err := cmd.Start(); err != nil {
		fmt.Printf("Failed to open URL: %v\n", err)
		return false
	}

	return true
}

func (l *WebLauncher) HandlesTab() bool {
	return false
}

func (l *WebLauncher) HandleTab(query string) string {
	return query
}

func (l *WebLauncher) Cleanup() {
}

type CalcLauncher struct {
	config *config.Config
}

func NewCalcLauncher() *CalcLauncher {
	return &CalcLauncher{}
}

func (l *CalcLauncher) Name() string {
	return "calc"
}

func (l *CalcLauncher) CommandTriggers() []string {
	return []string{"=", "calc", "math"}
}

func (l *CalcLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *CalcLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	if strings.TrimSpace(query) == "" {
		return nil
	}

	return []*LauncherItem{
		{
			Title:    fmt.Sprintf("Calculate: %s", query),
			Subtitle: "Evaluate expression",
			Icon:     "accessories-calculator",
			Command:  fmt.Sprintf("qalc %s", query),
			Launcher: l,
		},
	}
}

func (l *CalcLauncher) HandlesEnter() bool {
	return true
}

func (l *CalcLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	cmd := exec.Command("qalc", query)
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setsid: true,
	}

	if err := cmd.Start(); err != nil {
		fmt.Printf("Failed to calculate: %v\n", err)
		return false
	}

	return true
}

func (l *CalcLauncher) HandlesTab() bool {
	return false
}

func (l *CalcLauncher) HandleTab(query string) string {
	return query
}

func (l *CalcLauncher) Cleanup() {
}
