package launcher

import (
	"os/exec"
	"strconv"
	"strings"
	"syscall"

	"github.com/sigma/locus-go/internal/config"
)

type TimerLauncher struct {
	config *config.Config
}

func NewTimerLauncher(cfg *config.Config) *TimerLauncher {
	return &TimerLauncher{
		config: cfg,
	}
}

func (l *TimerLauncher) Name() string {
	return "timer"
}

func (l *TimerLauncher) CommandTriggers() []string {
	return []string{"timer", "t"}
}

func (l *TimerLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *TimerLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	presets := []struct {
		name  string
		value string
		cmd   string
	}{
		{"5 minutes", "5m", "sleep 300 && notify-send Timer \"5 minutes are up!\""},
		{"10 minutes", "10m", "sleep 600 && notify-send Timer \"10 minutes are up!\""},
		{"15 minutes", "15m", "sleep 900 && notify-send Timer \"15 minutes are up!\""},
		{"30 minutes", "30m", "sleep 1800 && notify-send Timer \"30 minutes are up!\""},
		{"1 hour", "1h", "sleep 3600 && notify-send Timer \"1 hour is up!\""},
		{"2 hours", "2h", "sleep 7200 && notify-send Timer \"2 hours are up!\""},
	}

	items := make([]*LauncherItem, 0, len(presets))
	for _, p := range presets {
		items = append(items, &LauncherItem{
			Title:    p.name,
			Subtitle: "Timer preset",
			Icon:     "alarm-symbolic",
			Command:  p.cmd,
		})
	}

	q := strings.TrimSpace(query)
	if q != "" {
		items = append(items, &LauncherItem{
			Title:    "Custom Timer: " + q,
			Subtitle: "Start custom timer",
			Icon:     "alarm-symbolic",
			Command:  l.parseTimerCommand(q),
		})
	}

	return items
}

func (l *TimerLauncher) parseTimerCommand(query string) string {
	parts := strings.Fields(query)
	if len(parts) == 0 {
		return ""
	}

	var seconds int
	for _, p := range parts {
		if strings.HasSuffix(p, "m") || strings.HasSuffix(p, "min") {
			val, _ := strconv.Atoi(strings.TrimSuffix(strings.TrimSuffix(p, "m"), "min"))
			seconds += val * 60
		} else if strings.HasSuffix(p, "h") || strings.HasSuffix(p, "hr") {
			val, _ := strconv.Atoi(strings.TrimSuffix(strings.TrimSuffix(p, "h"), "hr"))
			seconds += val * 3600
		} else if strings.HasSuffix(p, "s") || strings.HasSuffix(p, "sec") {
			val, _ := strconv.Atoi(strings.TrimSuffix(strings.TrimSuffix(p, "s"), "sec"))
			seconds += val
		} else {
			val, _ := strconv.Atoi(p)
			seconds += val
		}
	}

	if seconds <= 0 {
		seconds = 300
	}

	return "sleep " + strconv.Itoa(seconds) + " && notify-send Timer \"Time is up!\""
}

func (l *TimerLauncher) HandlesEnter() bool {
	return true
}

func (l *TimerLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	cmd := exec.Command("sh", "-c", l.parseTimerCommand(query))
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	return cmd.Start() == nil
}

func (l *TimerLauncher) HandlesTab() bool {
	return false
}

func (l *TimerLauncher) HandleTab(query string) string {
	return query
}

func (l *TimerLauncher) Cleanup() {
}
