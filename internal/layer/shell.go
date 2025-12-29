package layer

/*
#cgo pkg-config: gtk-layer-shell-0
#include <gtk-layer-shell.h>
*/
import "C"
import (
	"unsafe"

	"github.com/gotk3/gotk3/gdk"
)

func InitForWindow(window unsafe.Pointer) {
	C.gtk_layer_init_for_window((*C.GtkWindow)(window))
}

func SetMonitor(window unsafe.Pointer, monitor *gdk.Monitor) {
	if monitor == nil {
		C.gtk_layer_set_monitor((*C.GtkWindow)(window), nil)
	} else {
		C.gtk_layer_set_monitor((*C.GtkWindow)(window), (*C.GdkMonitor)(unsafe.Pointer(monitor.Native())))
	}
}

func SetMonitorByIndex(window unsafe.Pointer, display *gdk.Display, index int) error {
	monitor, err := display.GetMonitor(index)
	if err != nil {
		return err
	}
	C.gtk_layer_set_monitor((*C.GtkWindow)(window), (*C.GdkMonitor)(unsafe.Pointer(monitor.Native())))
	return nil
}

func SetLayer(window unsafe.Pointer, layer Layer) {
	C.gtk_layer_set_layer((*C.GtkWindow)(window), C.GtkLayerShellLayer(layer))
}

func SetAnchor(window unsafe.Pointer, edge Edge, anchorTo bool) {
	var anchor C.gboolean
	if anchorTo {
		anchor = 1
	}
	C.gtk_layer_set_anchor((*C.GtkWindow)(window), C.GtkLayerShellEdge(edge), anchor)
}

func SetExclusiveZone(window unsafe.Pointer, zone int) {
	C.gtk_layer_set_exclusive_zone((*C.GtkWindow)(window), C.int(zone))
}

func AutoExclusiveZoneEnable(window unsafe.Pointer) {
	C.gtk_layer_auto_exclusive_zone_enable((*C.GtkWindow)(window))
}

func SetMargin(window unsafe.Pointer, edge Edge, margin int) {
	C.gtk_layer_set_margin((*C.GtkWindow)(window), C.GtkLayerShellEdge(edge), C.int(margin))
}

func SetKeyboardMode(window unsafe.Pointer, mode KeyboardMode) {
	C.gtk_layer_set_keyboard_mode((*C.GtkWindow)(window), C.GtkLayerShellKeyboardMode(mode))
}

type Layer int

const (
	LayerBackground Layer = 0
	LayerBottom     Layer = 1
	LayerTop        Layer = 2
	LayerOverlay    Layer = 3
)

type Edge int

const (
	EdgeLeft   Edge = 0
	EdgeRight  Edge = 1
	EdgeTop    Edge = 2
	EdgeBottom Edge = 3
)

type KeyboardMode int

const (
	KeyboardModeNone      KeyboardMode = 0
	KeyboardModeExclusive KeyboardMode = 1
	KeyboardModeOnDemand  KeyboardMode = 2
)
