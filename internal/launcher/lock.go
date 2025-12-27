package launcher

import (
	"fmt"

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
	socketPath := l.config.SocketPath
	return []*LauncherItem{
		{
			Title:      "Lock Screen",
			Subtitle:   "Lock the screen immediately",
			Icon:       "system-lock-screen-symbolic",
			ActionData: NewShellAction(fmt.Sprintf("echo 'lock' | nc -U %s", socketPath)),
		},
	}
}

func (l *LockLauncher) GetHooks() []Hook {
	return []Hook{}
}

func (l *LockLauncher) Rebuild(ctx *LauncherContext) error {
	return nil
}

func (l *LockLauncher) Cleanup() {
}

func (l *LockLauncher) GetCtrlNumberAction(number int) (CtrlNumberAction, bool) {
	return nil, false
}
