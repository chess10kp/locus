package launcher

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/sigma/locus-go/internal/config"
)

type TimerLauncher struct {
	config      *config.Config
	timerActive bool
	timerMutex  sync.Mutex
	cancelFunc  context.CancelFunc
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
	if prefixes, ok := l.config.Launcher.LauncherPrefixes["timer"]; ok && prefixes != "" {
		return []string{prefixes}
	}
	return []string{"%"}
}

func (l *TimerLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *TimerLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	items := []*LauncherItem{}

	timeStr := strings.TrimSpace(query)

	if timeStr == "" {
		items = append(items, &LauncherItem{
			Title:    "Usage: %5m",
			Subtitle: "Enter time duration (e.g., 5m, 1h, 30s)",
			Icon:     "clock",
			Launcher: l,
		})
	} else {
		seconds := l.parseTime(timeStr)
		if seconds != nil && *seconds > 0 {
			displayTime := l.formatDuration(time.Duration(*seconds) * time.Second)
			items = append(items, &LauncherItem{
				Title:      fmt.Sprintf("Set timer for %s", timeStr),
				Subtitle:   fmt.Sprintf("Duration: %s", displayTime),
				Icon:       "clock",
				ActionData: NewTimerAction("start", timeStr),
				Launcher:   l,
			})
		} else {
			items = append(items, &LauncherItem{
				Title:    "Invalid time format",
				Subtitle: "Use format like 5m, 1h, 30s",
				Icon:     "dialog-error",
				Launcher: l,
			})
		}
	}

	return items
}

func (l *TimerLauncher) parseTime(timeStr string) *int {
	re := regexp.MustCompile(`^(\d+)([hms])$`)
	match := re.FindStringSubmatch(timeStr)
	if match == nil {
		return nil
	}

	num := 0
	fmt.Sscanf(match[1], "%d", &num)
	unit := match[2]

	var seconds int
	switch unit {
	case "h":
		seconds = num * 3600
	case "m":
		seconds = num * 60
	case "s":
		seconds = num
	default:
		return nil
	}

	return &seconds
}

func (l *TimerLauncher) formatDuration(d time.Duration) string {
	hours := int(d.Hours())
	minutes := int(d.Minutes()) % 60
	seconds := int(d.Seconds()) % 60

	if hours > 0 {
		return fmt.Sprintf("%dh %dm %ds", hours, minutes, seconds)
	} else if minutes > 0 {
		return fmt.Sprintf("%dm %ds", minutes, seconds)
	}
	return fmt.Sprintf("%ds", seconds)
}

func (l *TimerLauncher) startTimer(timeStr string) error {
	seconds := l.parseTime(timeStr)
	if seconds == nil || *seconds <= 0 {
		return fmt.Errorf("invalid time format: %s", timeStr)
	}

	l.timerMutex.Lock()
	defer l.timerMutex.Unlock()

	if l.timerActive {
		l.cancelFunc()
	}

	ctx, cancel := context.WithCancel(context.Background())
	l.cancelFunc = cancel
	l.timerActive = true

	initialDisplay := l.formatDuration(time.Duration(*seconds) * time.Second)
	l.sendIPCMessage(fmt.Sprintf("timer:%s", initialDisplay))

	go l.runTimer(ctx, *seconds)

	cmd := exec.Command("notify-send", "-a", "Timer", fmt.Sprintf("Timer set for %s", timeStr))
	cmd.Env = os.Environ()
	_ = cmd.Run()

	return nil
}

func (l *TimerLauncher) runTimer(ctx context.Context, totalSeconds int) {
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()

	remaining := totalSeconds

	for {
		select {
		case <-ctx.Done():
			l.sendIPCMessage("timer:clear")
			l.timerMutex.Lock()
			l.timerActive = false
			l.timerMutex.Unlock()
			return
		case <-ticker.C:
			remaining--
			if remaining <= 0 {
				l.timerComplete(totalSeconds)
				l.sendIPCMessage("timer:clear")
				l.timerMutex.Lock()
				l.timerActive = false
				l.timerMutex.Unlock()
				return
			}
			display := l.formatDuration(time.Duration(remaining) * time.Second)
			l.sendIPCMessage(fmt.Sprintf("timer:%s", display))
		}
	}
}

func (l *TimerLauncher) timerComplete(totalSeconds int) {
	cmd := exec.Command("notify-send", "-a", "Timer", "-t", "3000", "Timer complete")
	cmd.Env = os.Environ()
	_ = cmd.Run()

	soundPath := "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"
	cmd = exec.Command("mpv", "--no-video", soundPath)
	cmd.Env = os.Environ()
	_ = cmd.Start()
}

func (l *TimerLauncher) sendIPCMessage(message string) {
	socketPath := l.config.SocketPath
	conn, err := net.Dial("unix", socketPath)
	if err != nil {
		return
	}
	defer conn.Close()

	fullMessage := fmt.Sprintf("statusbar:%s", message)
	_, _ = conn.Write([]byte(fullMessage))
}

func (l *TimerLauncher) GetHooks() []Hook {
	return []Hook{NewTimerHook(l)}
}

func (l *TimerLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *TimerLauncher) Cleanup() {
	l.timerMutex.Lock()
	if l.timerActive && l.cancelFunc != nil {
		l.cancelFunc()
		l.timerActive = false
	}
	l.timerMutex.Unlock()
}

func (l *TimerLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}

type TimerHook struct {
	launcher *TimerLauncher
}

func NewTimerHook(launcher *TimerLauncher) *TimerHook {
	return &TimerHook{launcher: launcher}
}

func (h *TimerHook) getTrigger() string {
	triggers := h.launcher.CommandTriggers()
	if len(triggers) > 0 {
		return triggers[0]
	}
	return "%"
}

func (h *TimerHook) ID() string {
	return "timer_hook"
}

func (h *TimerHook) Priority() int {
	return 100
}

func (h *TimerHook) OnSelect(execCtx context.Context, ctx *HookContext, data ActionData) HookResult {
	if timerAction, ok := data.(*TimerAction); ok {
		if timerAction.Action == "start" {
			_ = h.launcher.startTimer(timerAction.Value)
			return HookResult{Handled: true}
		}
	}
	return HookResult{Handled: false}
}

func (h *TimerHook) OnEnter(execCtx context.Context, ctx *HookContext, text string) HookResult {
	trigger := h.getTrigger()
	if strings.HasPrefix(text, trigger) {
		timeStr := strings.TrimSpace(text[len(trigger):])
		if timeStr != "" {
			_ = h.launcher.startTimer(timeStr)
			return HookResult{Handled: true}
		}
	}
	return HookResult{Handled: false}
}

func (h *TimerHook) OnTab(execCtx context.Context, ctx *HookContext, text string) TabResult {
	return TabResult{Handled: false}
}

func (h *TimerHook) Cleanup() {}
