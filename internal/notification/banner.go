package notification

import (
	"fmt"
	"sync"
	"time"
	"unsafe"

	"github.com/gotk3/gotk3/gdk"
	"github.com/gotk3/gotk3/glib"
	"github.com/gotk3/gotk3/gtk"
	"github.com/gotk3/gotk3/pango"
	"github.com/chess10kp/locus/internal/layer"
)

var (
	urgencyColors = map[Urgency]string{
		UrgencyLow:      "#50fa7b",
		UrgencyNormal:   "#f1fa8c",
		UrgencyCritical: "#ff5555",
	}
)

type Banner struct {
	notification  *Notification
	window        *gtk.Window
	container     *gtk.Box
	onClose       func(string)
	onAction      func(string, string)
	dismissTimer  *time.Timer
	timeout       int
	position      *BannerPosition
	animating     bool
	currentMargin int
	mu            sync.Mutex
}

func NewBanner(notif *Notification, onClose func(string), onAction func(string, string)) (*Banner, error) {
	b := &Banner{
		notification:  notif,
		onClose:       onClose,
		onAction:      onAction,
		timeout:       notif.ExpireTimeout,
		currentMargin: -800,
	}

	if b.timeout == 0 {
		b.timeout = 5000
	}

	if err := b.createWindow(); err != nil {
		return nil, err
	}

	if err := b.buildUI(); err != nil {
		return nil, err
	}

	b.setupLayerShell()

	if b.timeout > 0 && notif.Urgency != UrgencyCritical {
		b.startDismissTimer()
	}

	b.animateIn()

	return b, nil
}

func (b *Banner) createWindow() error {
	win, err := gtk.WindowNew(gtk.WINDOW_TOPLEVEL)
	if err != nil {
		return fmt.Errorf("failed to create banner window: %w", err)
	}

	win.SetTitle("Notification")
	win.SetResizable(false)
	win.SetDecorated(false)
	win.SetDefaultSize(400, 100)

	b.window = win

	return nil
}

func (b *Banner) setupLayerShell() {
	obj := unsafe.Pointer(b.window.GObject)
	layer.InitForWindow(obj)
	layer.SetLayer(obj, layer.LayerOverlay)
	layer.SetKeyboardMode(obj, layer.KeyboardModeNone)
	layer.SetAnchor(obj, layer.EdgeTop, true)
	layer.SetAnchor(obj, layer.EdgeRight, true)
	layer.SetMargin(obj, layer.EdgeRight, b.currentMargin)
}

func (b *Banner) buildUI() error {
	mainBox, err := gtk.BoxNew(gtk.ORIENTATION_HORIZONTAL, 10)
	if err != nil {
		return fmt.Errorf("failed to create main box: %w", err)
	}

	mainBox.SetMarginStart(10)
	mainBox.SetMarginEnd(10)
	mainBox.SetMarginTop(10)
	mainBox.SetMarginBottom(10)

	borderColor := urgencyColors[b.notification.Urgency]
	css := fmt.Sprintf(`
		box {
			background-color: rgba(14, 20, 25, 0.95);
			border-left: 3px solid %s;
		}
	`, borderColor)

	applyCSS(mainBox, css)

	if b.notification.AppIcon != "" {
		iconBox, err := b.createIconBox()
		if err == nil {
			mainBox.PackStart(iconBox, false, false, 0)
		}
	}

	contentBox, err := b.createContentBox()
	if err != nil {
		return err
	}
	mainBox.PackStart(contentBox, true, true, 0)

	actionBox, err := b.createActionBox()
	if err == nil && actionBox != nil {
		mainBox.PackStart(actionBox, false, false, 0)
	}

	closeButton, err := b.createCloseButton()
	if err == nil {
		mainBox.PackStart(closeButton, false, false, 0)
	}

	b.window.Add(mainBox)
	b.container = mainBox

	mainBox.Connect("button-press-event", b.onBannerClicked)
	mainBox.Connect("enter-notify-event", b.onHoverEnter)

	return nil
}

func (b *Banner) createIconBox() (*gtk.Box, error) {
	iconBox, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 0)
	if err != nil {
		return nil, err
	}

	image, err := gtk.ImageNew()
	if err != nil {
		return nil, err
	}

	image.SetPixelSize(48)

	iconName := b.notification.AppIcon
	if iconName == "" {
		iconName = "dialog-information"
	}

	if pixbuf, err := loadImageIcon(iconName, 48); err == nil {
		image.SetFromPixbuf(pixbuf)
	}

	iconBox.PackStart(image, false, false, 0)

	return iconBox, nil
}

func (b *Banner) createContentBox() (*gtk.Box, error) {
	contentBox, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 4)
	if err != nil {
		return nil, err
	}

	titleLabel, err := gtk.LabelNew(b.notification.Summary)
	if err != nil {
		return nil, err
	}

	titleLabel.SetHAlign(gtk.ALIGN_START)
	titleLabel.SetLineWrap(true)
	titleLabel.SetMaxWidthChars(40)
	titleLabel.SetEllipsize(pango.ELLIPSIZE_END)

	titleCSS := `
		label {
			font-weight: bold;
			font-size: 16px;
			color: #f8f8f2;
		}
	`
	applyCSS(titleLabel, titleCSS)
	contentBox.PackStart(titleLabel, false, false, 0)

	if b.notification.Body != "" {
		bodyLabel, err := gtk.LabelNew(b.notification.Body)
		if err != nil {
			return nil, err
		}

		bodyLabel.SetHAlign(gtk.ALIGN_START)
		bodyLabel.SetLineWrap(true)
		bodyLabel.SetMaxWidthChars(40)
		bodyLabel.SetLines(3)
		bodyLabel.SetEllipsize(pango.ELLIPSIZE_END)

		bodyCSS := `
			label {
				font-size: 14px;
				color: #f8f8f2;
			}
		`
		applyCSS(bodyLabel, bodyCSS)
		contentBox.PackStart(bodyLabel, false, false, 0)
	}

	appLabel, err := gtk.LabelNew(b.notification.AppName)
	if err != nil {
		return nil, err
	}

	appLabel.SetHAlign(gtk.ALIGN_START)
	appLabel.SetSensitive(false)

	appCSS := `
		label {
			font-size: 12px;
			color: #6272a4;
		}
	`
	applyCSS(appLabel, appCSS)
	contentBox.PackStart(appLabel, false, false, 0)

	return contentBox, nil
}

func (b *Banner) createActionBox() (*gtk.Box, error) {
	if len(b.notification.Actions) == 0 {
		return nil, nil
	}

	actionBox, err := gtk.BoxNew(gtk.ORIENTATION_VERTICAL, 4)
	if err != nil {
		return nil, err
	}

	for _, action := range b.notification.Actions {
		button, err := gtk.ButtonNewWithLabel(action.Label)
		if err != nil {
			continue
		}

		buttonCSS := `
			button {
				padding: 4px 12px;
				font-size: 12px;
				color: #8be9fd;
				background: rgba(139, 233, 253, 0.1);
				border: 1px solid #8be9fd;
			}
			button:hover {
				background: rgba(139, 233, 253, 0.2);
			}
		`
		applyCSS(button, buttonCSS)

		actionKey := action.Key
		button.Connect("clicked", func() {
			if b.onAction != nil {
				b.onAction(b.notification.ID, actionKey)
			}
		})

		actionBox.PackStart(button, false, false, 0)
	}

	return actionBox, nil
}

func (b *Banner) createCloseButton() (*gtk.Button, error) {
	button, err := gtk.ButtonNewWithLabel("×")
	if err != nil {
		return nil, err
	}

	closeCSS := `
		button {
			padding: 4px 8px;
			font-size: 18px;
			color: #8be9fd;
			background: none;
		}
		button:hover {
			color: #ff5555;
			background: rgba(255, 85, 85, 0.2);
		}
	`
	applyCSS(button, closeCSS)

	button.Connect("clicked", b.onCloseClicked)

	return button, nil
}

func (b *Banner) Show() {
	b.window.ShowAll()
}

func (b *Banner) Dismiss() {
	b.mu.Lock()
	defer b.mu.Unlock()

	if b.animating {
		return
	}

	b.stopDismissTimerLocked()
	b.animateOut(func() {
		b.window.Destroy()
		if b.onClose != nil {
			b.onClose(b.notification.ID)
		}
	})
}

func (b *Banner) UpdatePosition(x, y int) {
	b.mu.Lock()
	b.currentMargin = x
	obj := unsafe.Pointer(b.window.GObject)
	layer.SetMargin(obj, layer.EdgeTop, y)
	layer.SetMargin(obj, layer.EdgeRight, x)
	b.position = &BannerPosition{X: x, Y: y}
	b.mu.Unlock()
}

func (b *Banner) startDismissTimer() {
	b.mu.Lock()
	defer b.mu.Unlock()

	if b.dismissTimer != nil {
		b.dismissTimer.Stop()
	}

	b.dismissTimer = time.AfterFunc(time.Duration(b.timeout)*time.Millisecond, func() {
		glib.IdleAdd(func() {
			b.Dismiss()
		})
	})
}

func (b *Banner) stopDismissTimerLocked() {
	if b.dismissTimer != nil {
		b.dismissTimer.Stop()
		b.dismissTimer = nil
	}
}

func (b *Banner) animateIn() {
	b.mu.Lock()
	b.animating = true
	b.currentMargin = -800
	targetMargin := 10
	obj := unsafe.Pointer(b.window.GObject)
	b.mu.Unlock()

	glib.TimeoutAdd(16, func() bool {
		b.mu.Lock()
		defer b.mu.Unlock()

		if b.currentMargin < targetMargin {
			b.currentMargin = min(b.currentMargin+20, targetMargin)
			layer.SetMargin(obj, layer.EdgeRight, b.currentMargin)
			return true
		}

		b.animating = false
		return false
	})
}

func (b *Banner) animateOut(callback func()) {
	b.mu.Lock()
	b.animating = true
	targetMargin := -800
	obj := unsafe.Pointer(b.window.GObject)
	b.mu.Unlock()

	glib.TimeoutAdd(16, func() bool {
		b.mu.Lock()
		defer b.mu.Unlock()

		if b.currentMargin > targetMargin {
			b.currentMargin = max(b.currentMargin-20, targetMargin)
			layer.SetMargin(obj, layer.EdgeRight, b.currentMargin)
			return true
		}

		b.animating = false
		if callback != nil {
			callback()
		}
		return false
	})
}

func (b *Banner) onCloseClicked() {
	b.Dismiss()
}

func (b *Banner) onBannerClicked() {
	b.Dismiss()
}

func (b *Banner) onHoverEnter() {
	if b.notification.Urgency != UrgencyCritical {
		b.mu.Lock()
		b.stopDismissTimerLocked()
		b.mu.Unlock()
	}
}

func applyCSS(widget gtk.IWidget, css string) {
	cssProvider, _ := gtk.CssProviderNew()
	cssProvider.LoadFromData(css)

	styleContext, err := widget.ToWidget().GetStyleContext()
	if err == nil {
		styleContext.AddProvider(cssProvider, gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
	}
}

func loadImageIcon(iconName string, size int) (*gdk.Pixbuf, error) {
	iconTheme, err := gtk.IconThemeGetDefault()
	if err != nil {
		return nil, err
	}

	return iconTheme.LoadIcon(iconName, size, gtk.ICON_LOOKUP_FORCE_SIZE)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
