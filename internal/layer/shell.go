package layer

/*
#cgo pkg-config: gtk-layer-shell-0
#include <gtk-layer-shell.h>
*/
import "C"
import "unsafe"

// InitForWindow initializes a window as a layer shell surface
func InitForWindow(window unsafe.Pointer) {
	C.gtk_layer_init_for_window((*C.GtkWindow)(window))
}

// SetLayer sets the layer for a layer shell surface
func SetLayer(window unsafe.Pointer, layer Layer) {
	C.gtk_layer_set_layer((*C.GtkWindow)(window), C.GtkLayerShellLayer(layer))
}

// SetAnchor sets which edges to anchor the window to
func SetAnchor(window unsafe.Pointer, edge Edge, anchorTo bool) {
	var anchor C.gboolean
	if anchorTo {
		anchor = 1
	}
	C.gtk_layer_set_anchor((*C.GtkWindow)(window), C.GtkLayerShellEdge(edge), anchor)
}

// SetExclusiveZone sets the exclusive zone for the surface
// This prevents other windows from occupying the same space
func SetExclusiveZone(window unsafe.Pointer, zone int) {
	C.gtk_layer_set_exclusive_zone((*C.GtkWindow)(window), C.int(zone))
}

// AutoExclusiveZoneEnable automatically sets the exclusive zone
// to match the window's size when anchored to edges
func AutoExclusiveZoneEnable(window unsafe.Pointer) {
	C.gtk_layer_auto_exclusive_zone_enable((*C.GtkWindow)(window))
}

// SetMargin sets the margin for a specific edge
func SetMargin(window unsafe.Pointer, edge Edge, margin int) {
	C.gtk_layer_set_margin((*C.GtkWindow)(window), C.GtkLayerShellEdge(edge), C.int(margin))
}

// SetKeyboardMode sets the keyboard interactivity mode
func SetKeyboardMode(window unsafe.Pointer, mode KeyboardMode) {
	C.gtk_layer_set_keyboard_mode((*C.GtkWindow)(window), C.GtkLayerShellKeyboardMode(mode))
}

// Layer represents a layer shell layer
type Layer int

const (
	LayerBackground Layer = 0
	LayerBottom     Layer = 1
	LayerTop        Layer = 2
	LayerOverlay    Layer = 3
)

// Edge represents a screen edge
type Edge int

const (
	EdgeLeft   Edge = 0
	EdgeRight  Edge = 1
	EdgeTop    Edge = 2
	EdgeBottom Edge = 3
)

// KeyboardMode represents keyboard focus mode
type KeyboardMode int

const (
	KeyboardModeNone      KeyboardMode = 0
	KeyboardModeExclusive KeyboardMode = 1
	KeyboardModeOnDemand  KeyboardMode = 2
)
