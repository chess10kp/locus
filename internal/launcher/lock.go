package launcher

import (
	"os/exec"
	"syscall"

	"github.com/sigma/locus-go/internal/config"
)

type LockLauncher struct {
	config *config.Config
}

func NewLockLauncher(cfg *config.Config) *LockLauncher {
	return &LockLauncher{
		config: cfg,
	}
}

func (l *LockLauncher) Name() string {
	return "lock"
}

func (l *LockLauncher) CommandTriggers() []string {
	return []string{"lock", "screenlock", "lockscreen"}
}

func (l *LockLauncher) GetSizeMode() LauncherSizeMode {
	return LauncherSizeModeDefault
}

func (l *LockLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	return []*LauncherItem{
		{
			Title:    "Lock Screen",
			Subtitle: "Lock the screen immediately",
			Icon:     "system-lock-screen-symbolic",
			Command:  "swaylock -f -c 000000",
		},
	}
}

func (l *LockLauncher) HandlesEnter() bool {
	return true
}

func (l *LockLauncher) HandleEnter(query string, ctx *LauncherContext) bool {
	cmd := exec.Command("sh", "-c", "swaylock -f -c 000000")
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	return cmd.Start() == nil
}

func (l *LockLauncher) HandlesTab() bool {
	return false
}

func (l *LockLauncher) HandleTab(query string) string {
	return query
}

func (l *LockLauncher) Cleanup() {
}
