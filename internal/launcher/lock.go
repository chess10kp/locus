package launcher

import (
	"github.com/chess10kp/locus/internal/config"
)

type LockLauncher struct {
	config *config.Config
}

type LockLauncherFactory struct{}

func (f *LockLauncherFactory) Name() string {
	return "lock"
}

func (f *LockLauncherFactory) Create(cfg *config.Config) Launcher {
	return NewLockLauncher(cfg)
}

func init() {
	RegisterLauncherFactory(&LockLauncherFactory{})
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

func (l *LockLauncher) GetGridConfig() *GridConfig {
	return nil
}

func (l *LockLauncher) Populate(query string, ctx *LauncherContext) []*LauncherItem {
	return []*LauncherItem{
		{
			Title:      "Lock Screen",
			Subtitle:   "Lock the screen immediately",
			Icon:       "system-lock-screen-symbolic",
			ActionData: NewLockScreenAction("show"),
			Launcher:   l,
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
