package launcher

import (
	"context"
	"fmt"
	"os/exec"
	"strconv"
	"strings"
	"time"

	"github.com/chess10kp/locus/internal/config"
	"github.com/sahilm/fuzzy"
)

type Process struct {
	PID     int
	Name    string
	Command string
}

type KillLauncher struct {
	config    *config.Config
	processes []Process
}

type KillLauncherFactory struct{}

func (f *KillLauncherFactory) Name() string {
	return "kill"
}

func (f *KillLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewKillLauncher(cfg)
}

func init() {
	RegisterLauncherFactory(&KillLauncherFactory{})
}

func NewKillLauncher(cfg *config.Config) *KillLauncher {
	return &KillLauncher{
		config:    cfg,
		processes: []Process{},
	}
}

func (l *KillLauncher) Name() string {
	return "kill"
}

func (l *KillLauncher) CommandTriggers() []string {
	return []string{"kill", "k"}
}

func (l *KillLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *KillLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *KillLauncher) Populate(query string, launcherCtx *LauncherContext) []*LauncherItem {
	q := strings.TrimSpace(query)

	// Get processes with timeout
	cmdCtx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
	defer cancel()

	// Get process list - using ps to get PID, user, and command
	cmd := exec.CommandContext(cmdCtx, "ps", "-eo", "pid,comm,cmd", "--sort=-pid")
	output, err := cmd.Output()

	if err != nil {
		return []*LauncherItem{
			{
				Title:    "Error loading processes",
				Subtitle: err.Error(),
				Icon:     "dialog-error-symbolic",
				Launcher: l,
			},
		}
	}

	// Parse process list
	processes, err := l.parseProcesses(string(output))
	if err != nil {
		return []*LauncherItem{
			{
				Title:    "Error parsing processes",
				Subtitle: err.Error(),
				Icon:     "dialog-error-symbolic",
				Launcher: l,
			},
		}
	}

	l.processes = processes

	// Filter by query
	if q != "" {
		return l.filterProcesses(q)
	}

	// Return top processes
	maxResults := 20
	if len(processes) > maxResults {
		processes = processes[:maxResults]
	}

	return l.processesToItems(processes)
}

func (l *KillLauncher) parseProcesses(output string) ([]Process, error) {
	processes := []Process{}
	lines := strings.Split(output, "\n")

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}

		pid, err := strconv.Atoi(fields[0])
		if err != nil {
			continue
		}

		name := fields[1]
		command := strings.Join(fields[2:], " ")

		// Skip system processes and kernel threads
		if name == "[kthreadd]" || strings.HasPrefix(name, "[") {
			continue
		}

		processes = append(processes, Process{
			PID:     pid,
			Name:    name,
			Command: command,
		})
	}

	return processes, nil
}

func (l *KillLauncher) filterProcesses(query string) []*LauncherItem {
	// Get process names for fuzzy search
	names := make([]string, len(l.processes))
	pidMap := make(map[string]int)

	for i, proc := range l.processes {
		names[i] = proc.Name
		pidMap[proc.Name] = i
	}

	// Use fuzzy search
	matches := fuzzy.Find(query, names)

	maxResults := 20
	items := make([]*LauncherItem, 0, minInt(len(matches), maxResults))

	for i := 0; i < len(matches) && i < maxResults; i++ {
		match := matches[i]
		if idx, ok := pidMap[match.Str]; ok {
			items = append(items, l.processToItem(l.processes[idx]))
		}
	}

	return items
}

func (l *KillLauncher) processToItem(proc Process) *LauncherItem {
	return &LauncherItem{
		Title:      fmt.Sprintf("%s (PID: %d)", proc.Name, proc.PID),
		Subtitle:   proc.Command,
		Icon:       "process-stop-symbolic",
		ActionData: NewShellAction(fmt.Sprintf("kill %d", proc.PID)),
		Launcher:   l,
	}
}

func (l *KillLauncher) processesToItems(processes []Process) []*LauncherItem {
	items := make([]*LauncherItem, 0, len(processes))
	for _, proc := range processes {
		items = append(items, l.processToItem(proc))
	}
	return items
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func (l *KillLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *KillLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *KillLauncher) Cleanup() {
}

func (l *KillLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}
