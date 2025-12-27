package lockscreen

/*
#cgo pkg-config: gtk-layer-shell-0
#include <gtk-layer-shell.h>
*/
import "C"
import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"log"
	"sync"
	"unsafe"

	"github.com/gotk3/gotk3/gdk"
	"github.com/gotk3/gotk3/glib"
	"github.com/gotk3/gotk3/gtk"
	"github.com/chess10kp/locus/internal/config"
	"github.com/chess10kp/locus/internal/layer"
)

var debugLogger = log.New(log.Writer(), "[LOCKSCREEN-DEBUG] ", log.LstdFlags|log.Lmicroseconds)

type LockScreenWindow struct {
	window              *gtk.Window
	passwordEntry       *gtk.Entry
	statusLabel         *gtk.Label
	lockedLabel         *gtk.Label
	centerBox           *gtk.Box
	monitor             *gdk.Monitor
	isInputEnabled      bool
	correctPasswordHash string
	attempts            int
	maxAttempts         int
	unlockCallback      func()
}

type LockScreenManager struct {
	config         *config.Config
	lockScreens    []*LockScreenWindow
	mu             sync.RWMutex
	locked         bool
	destroying     bool
	monitorHandler glib.SignalHandle
}

func NewLockScreenManager(cfg *config.Config) *LockScreenManager {
	return &LockScreenManager{
		config:      cfg,
		lockScreens: make([]*LockScreenWindow, 0),
		locked:      false,
	}
}

func (m *LockScreenManager) Show() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.locked {
		debugLogger.Println("Already locked")
		return nil
	}

	if !m.config.LockScreen.Enabled {
		log.Println("Lockscreen is disabled in config")
		return nil
	}

	debugLogger.Println("Creating lock screens for all monitors")

	display, err := gdk.DisplayGetDefault()
	if err != nil {
		return fmt.Errorf("failed to get default display: %w", err)
	}

	nMonitors := display.GetNMonitors()
	if nMonitors == 0 {
		return fmt.Errorf("no monitors available")
	}

	debugLogger.Printf("Found %d monitors", nMonitors)

	for i := 0; i < nMonitors; i++ {
		monitor, err := display.GetMonitor(i)
		if err != nil {
			log.Printf("Failed to get monitor %d: %v", i, err)
			continue
		}

		isInputEnabled := i == 0
		lockScreen, err := m.createLockScreenWindow(monitor, isInputEnabled)
		if err != nil {
			log.Printf("Failed to create lock screen for monitor %d: %v", i, err)
			continue
		}

		m.lockScreens = append(m.lockScreens, lockScreen)
		debugLogger.Printf("Created lock screen for monitor %d (input=%v)", i, isInputEnabled)
	}

	m.locked = true

	for _, ls := range m.lockScreens {
		m.showLockScreenWindow(ls)
	}

	m.setupMonitorChangeHandler()

	debugLogger.Println("Lock screen activated")
	return nil
}

func (m *LockScreenManager) Hide() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if !m.locked {
		return nil
	}

	debugLogger.Println("Hiding all lock screens")

	for _, ls := range m.lockScreens {
		if ls.window != nil {
			ls.window.Hide()
			ls.window.Destroy()
		}
	}

	m.lockScreens = make([]*LockScreenWindow, 0)
	m.locked = false
	m.destroying = false

	if m.monitorHandler != 0 {
		display, _ := gdk.DisplayGetDefault()
		if display != nil {
			display.HandlerDisconnect(m.monitorHandler)
			m.monitorHandler = 0
		}
	}

	debugLogger.Println("Lock screen deactivated")
	return nil
}

func (m *LockScreenManager) IsLocked() bool {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.locked
}

func (m *LockScreenManager) UnlockAll() {
	m.Hide()
}

func (m *LockScreenManager) createLockScreenWindow(monitor *gdk.Monitor, isInputEnabled bool) (*LockScreenWindow, error) {
	window, err := gtk.WindowNew(gtk.WINDOW_TOPLEVEL)
	if err != nil {
		return nil, fmt.Errorf("failed to create window: %w", err)
	}

	window.SetDecorated(false)
	window.SetSkipTaskbarHint(true)
	window.SetSkipPagerHint(true)
	window.SetResizable(false)
	window.SetTitle("locus-lockscreen")
	window.SetName("lockscreen-window")

	geo := monitor.GetGeometry()
	window.SetDefaultSize(geo.GetWidth(), geo.GetHeight())

	ls := &LockScreenWindow{
		window:         window,
		monitor:        monitor,
		isInputEnabled: isInputEnabled,
		maxAttempts:    m.config.LockScreen.MaxAttempts,
		attempts:       0,
	}

	if m.config.LockScreen.PasswordHash != "" {
		ls.correctPasswordHash = m.config.LockScreen.PasswordHash
	} else if m.config.LockScreen.Password != "" {
		hash := sha256.Sum256([]byte(m.config.LockScreen.Password))
		ls.correctPasswordHash = hex.EncodeToString(hash[:])
	} else {
		return nil, fmt.Errorf("no password configured")
	}

	if err := m.buildLockScreenUI(ls); err != nil {
		return nil, fmt.Errorf("failed to build UI: %w", err)
	}

	m.setupKeyHandlers(ls)
	m.setupCloseHandler(ls)

	return ls, nil
}

func (m *LockScreenManager) buildLockScreenUI(ls *LockScreenWindow) error {
	mainBox, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 0)
	if err != nil {
		return err
	}
	mainBox.SetVAlign(gtk.ALIGN_FILL)
	mainBox.SetHAlign(gtk.ALIGN_FILL)
	ls.window.Add(mainBox)

	centerBox, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 20)
	if err != nil {
		return err
	}
	centerBox.SetVAlign(gtk.ALIGN_CENTER)
	centerBox.SetHAlign(gtk.ALIGN_CENTER)
	centerBox.SetMarginBottom(40)
	centerBox.SetMarginTop(40)
	centerBox.SetMarginStart(40)
	centerBox.SetMarginEnd(40)
	ls.centerBox = centerBox

	if ls.isInputEnabled {
		passwordEntry, err := gtk.EntryNew()
		if err != nil {
			return err
		}
		passwordEntry.SetVisibility(false)
		passwordEntry.SetPlaceholderText("Enter password to unlock")
		passwordEntry.SetWidthChars(30)
		passwordEntry.SetHAlign(gtk.ALIGN_CENTER)
		passwordEntry.SetMarginStart(20)
		passwordEntry.SetMarginEnd(20)
		passwordEntry.SetName("lockscreen-entry")
		ls.passwordEntry = passwordEntry

		statusLabel, err := gtk.LabelNew("")
		if err != nil {
			return err
		}
		statusLabel.SetMarginTop(10)
		statusLabel.SetHAlign(gtk.ALIGN_CENTER)
		statusLabel.SetName("lockscreen-status")
		ls.statusLabel = statusLabel

		centerBox.PackStart(passwordEntry, false, false, 0)
		centerBox.PackStart(statusLabel, false, false, 0)

		ls.passwordEntry.Connect("activate", func() {
			m.checkPassword(ls)
		})
		ls.passwordEntry.Connect("changed", func() {
			ls.statusLabel.SetMarkup("")
		})
	} else {
		lockedLabel, err := gtk.LabelNew("Screen Locked")
		if err != nil {
			return err
		}
		lockedLabel.SetMarkup(`<span size="large" color="#ebdbb2">Screen Locked</span>`)
		lockedLabel.SetHAlign(gtk.ALIGN_CENTER)
		lockedLabel.SetName("lockscreen-label")
		ls.lockedLabel = lockedLabel

		centerBox.PackStart(lockedLabel, false, false, 0)
	}

	mainBox.PackStart(centerBox, true, true, 0)

	return nil
}

func (m *LockScreenManager) setupKeyHandlers(ls *LockScreenWindow) {
	ls.window.Connect("key-press-event", func(_ *gtk.Window, event *gdk.Event) bool {
		keyEvent := gdk.EventKeyNewFromEvent(event)
		if keyEvent == nil {
			return false
		}

		keyval := keyEvent.KeyVal()
		state := keyEvent.State()

		if ls.isInputEnabled && keyval == gdk.KEY_Escape {
			ls.passwordEntry.SetText("")
			return true
		}

		if state&gdk.CONTROL_MASK != 0 && state&gdk.MOD1_MASK != 0 && keyval == gdk.KEY_Tab {
			return true
		}

		if state&gdk.CONTROL_MASK != 0 && state&gdk.MOD1_MASK != 0 {
			switch keyval {
			case gdk.KEY_F1, gdk.KEY_F2, gdk.KEY_F3, gdk.KEY_F4,
				gdk.KEY_F5, gdk.KEY_F6, gdk.KEY_F7, gdk.KEY_F8,
				gdk.KEY_F9, gdk.KEY_F10, gdk.KEY_F11, gdk.KEY_F12:
				return true
			}
		}

		return false
	})
}

func (m *LockScreenManager) setupCloseHandler(ls *LockScreenWindow) {
	ls.window.Connect("close-request", func() bool {
		return true
	})
}

func (m *LockScreenManager) showLockScreenWindow(ls *LockScreenWindow) {
	geo := ls.monitor.GetGeometry()
	ls.window.SetDefaultSize(geo.GetWidth(), geo.GetHeight())

	windowPtr := unsafe.Pointer(ls.window.Native())
	layer.InitForWindow(windowPtr)
	layer.SetLayer(windowPtr, layer.LayerOverlay)
	layer.SetKeyboardMode(windowPtr, layer.KeyboardModeExclusive)
	layer.SetAnchor(windowPtr, layer.EdgeTop, true)
	layer.SetAnchor(windowPtr, layer.EdgeBottom, true)
	layer.SetAnchor(windowPtr, layer.EdgeLeft, true)
	layer.SetAnchor(windowPtr, layer.EdgeRight, true)
	layer.SetMargin(windowPtr, layer.EdgeTop, 0)
	layer.SetMargin(windowPtr, layer.EdgeBottom, 0)
	layer.SetMargin(windowPtr, layer.EdgeLeft, 0)
	layer.SetMargin(windowPtr, layer.EdgeRight, 0)
	layer.AutoExclusiveZoneEnable(windowPtr)

	C.gtk_layer_set_monitor((*C.GtkWindow)(windowPtr), (*C.GdkMonitor)(unsafe.Pointer(ls.monitor.Native())))

	ls.window.Show()

	if ls.isInputEnabled && ls.passwordEntry != nil {
		ls.passwordEntry.GrabFocus()
	}
}

func (m *LockScreenManager) checkPassword(ls *LockScreenWindow) {
	if !ls.isInputEnabled {
		return
	}

	text, _ := ls.passwordEntry.GetText()
	hash := sha256.Sum256([]byte(text))
	hashStr := hex.EncodeToString(hash[:])

	if hashStr == ls.correctPasswordHash {
		ls.statusLabel.SetMarkup(`<span color="#98c97c">Unlocking...</span>`)
		glib.TimeoutAdd(500, func() bool {
			m.UnlockAll()
			return false
		})
	} else {
		ls.attempts++
		remaining := ls.maxAttempts - ls.attempts

		if remaining > 0 {
			ls.statusLabel.SetMarkup(fmt.Sprintf(`<span color="#cc241d">Incorrect password! %d attempts remaining</span>`, remaining))
			ls.passwordEntry.SetText("")
			ls.passwordEntry.GrabFocus()
		} else {
			ls.statusLabel.SetMarkup(`<span color="#fb4934">Maximum attempts reached! Locking...</span>`)
			glib.TimeoutAdd(2000, func() bool {
				m.UnlockAll()
				return false
			})
		}
	}
}

func (m *LockScreenManager) setupMonitorChangeHandler() {
	display, err := gdk.DisplayGetDefault()
	if err != nil {
		return
	}

	m.monitorHandler = display.Connect("monitor-added", func(display *gdk.Display, monitor *gdk.Monitor) {
		m.mu.Lock()
		defer m.mu.Unlock()

		if !m.locked || m.destroying {
			return
		}

		debugLogger.Println("Monitor configuration changed, recreating lock screens")
		m.destroying = true
		m.UnlockAll()

		glib.TimeoutAdd(100, func() bool {
			m.destroying = false
			m.Show()
			return false
		})
	})
}

func (m *LockScreenManager) Cleanup() {
	m.Hide()
}
