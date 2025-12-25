package core

import (
	"log"
	"os"

	"github.com/gotk3/gotk3/gdk"
	"github.com/gotk3/gotk3/gtk"
)

const defaultStyles = `
* {
    font-family: "SF Pro Display", "Segoe UI", sans-serif;
    font-size: 14px;
}

#statusbar {
    background-color: #1e1e2e;
    color: #cdd6f4;
}

#launcher-window {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border-radius: 8px;
    border: 1px solid #313244;
}

#launcher-entry {
    background-color: #181825;
    color: #cdd6f4;
    padding: 12px;
    border: none;
    border-bottom: 1px solid #313244;
}

#launcher-entry:focus {
    border-bottom: 1px solid #89b4fa;
}

#result-list {
    background-color: transparent;
}

.list-row {
    padding: 12px;
    border-bottom: 1px solid #313244;
}

.list-row:hover {
    background-color: #313244;
}

.list-row:selected {
    background-color: #89b4fa;
    color: #1e1e2e;
}
`

var globalStyleProvider *gtk.CssProvider

func SetupStyles() {
	screen, err := gdk.ScreenGetDefault()
	if err != nil || screen == nil {
		log.Printf("Warning: Failed to get default screen: %v", err)
		return
	}

	provider, _ := gtk.CssProviderNew()
	if err := provider.LoadFromData(defaultStyles); err != nil {
		log.Printf("Warning: Failed to load default styles: %v", err)
		return
	}

	globalStyleProvider = provider
	gtk.AddProviderForScreen(screen, provider, gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
}

func LoadCustomCSS(path string) {
	screen, err := gdk.ScreenGetDefault()
	if err != nil || screen == nil {
		return
	}

	data, err := os.ReadFile(path)
	if err != nil {
		return
	}

	provider, _ := gtk.CssProviderNew()
	provider.LoadFromData(string(data))
	gtk.AddProviderForScreen(screen, provider, gtk.STYLE_PROVIDER_PRIORITY_USER)
}
