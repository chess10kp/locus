package layer

// Layer represents a layer shell layer
type Layer int

const (
	LayerBackground Layer = iota
	LayerBottom
	LayerTop
	LayerOverlay
)

// Edge represents window edges for anchoring
type Edge int

const (
	EdgeNone   Edge = 0
	EdgeTop    Edge = 1
	EdgeBottom Edge = 2
	EdgeLeft   Edge = 4
	EdgeRight  Edge = 8
)

// KeyboardMode represents keyboard focus mode
type KeyboardMode int

const (
	KeyboardModeNone KeyboardMode = iota
	KeyboardModeExclusive
	KeyboardModeOnDemand
)

// LayerShellContext holds a layer shell state
// This is a stub - actual Wayland layer shell integration requires
// protocol headers and CGO bindings
type LayerShellContext struct {
	Initialized bool
}

// InitLayerShell initializes the layer shell
// For now, this is a stub. Real implementation requires:
// - wayland-client library
// - wlr-layer-shell protocol headers
func InitLayerShell() *LayerShellContext {
	return &LayerShellContext{
		Initialized: true,
	}
}

// SetLayer sets the layer for a window
// This is managed via gotk3 window properties
func SetLayer(layer Layer) error {
	return nil
}

// SetAnchor sets the anchor edges for a window
// This is managed via gotk3 window properties
func SetAnchor(edges Edge) error {
	return nil
}

// SetMargin sets the margin from edges
func SetMargin(top, right, bottom, left int) error {
	return nil
}

// SetExclusiveZone sets the exclusive zone for a surface
func SetExclusiveZone(size int) error {
	return nil
}

// SetKeyboardMode sets the keyboard interactivity mode
func SetKeyboardMode(mode KeyboardMode) error {
	return nil
}

// Commit commits surface changes
func Commit() error {
	return nil
}

// Cleanup cleans up layer shell resources
func Cleanup() {
}
