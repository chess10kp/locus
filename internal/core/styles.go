package core

import (
	"fmt"
	"log"
	"os"

	"github.com/gotk3/gotk3/gdk"
	"github.com/gotk3/gotk3/gtk"
	"github.com/sigma/locus-go/internal/config"
)

const defaultStyles = `
* {
    font-family: "Iosevka", monospace;
    font-size: 16px;
    font-weight: bold;
    margin: 0;
    padding: 0;
    transition: opacity 0.2s ease;
}

label {
    color: #ebdbb2;
    font-size: 16px;
    font-weight: bold;
    font-family: "Iosevka", monospace;
    margin: 0;
    padding: 0;
    transition: opacity 0.2s ease;
}

window {
    background-color: #0e1419;
    border-bottom: 1px solid #444444;
}

#main-box, box {
    background-color: #0e1419;
}

.workspace-highlight {
    background-color: #50fa7b;
    border-radius: 2px;
}

.separator {
    color: #888888;
    font-size: 18px;
    font-family: monospace;
}

#statusbar {
    background-color: #0e1419;
    color: #ebdbb2;
}

#lockscreen-window {
    background: #0e1419;
    color: #ebdbb2;
}

#lockscreen-entry {
    background: #0e1419;
    color: #ebdbb2;
    border: none;
    outline: none;
    box-shadow: none;
    padding: 12px;
    font-size: 16px;
    font-family: "Iosevka", monospace;
}

#lockscreen-entry:focus {
    border: none;
    outline: none;
    box-shadow: none;
}

#lockscreen-entry:focus-visible {
    border: none;
    outline: none;
    box-shadow: none;
}

#lockscreen-status {
    font-family: "Iosevka", sans-serif;
    font-size: 14px;
}

#lockscreen-label {
    font-family: "Iosevka", sans-serif;
    font-size: 24px;
    font-weight: bold;
}
`

const defaultLauncherStyles = `
#launcher-window {
    background-color: #0e1419;
    color: #ebdbb2;
    border-radius: 8px;
    border: 1px solid #313244;
}

#launcher-entry {
    background-color: #181825;
    color: #ebdbb2;
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

#list-row {
    padding: 8px 12px;
    border-bottom: 1px solid #313244;
    min-height: 40px;
}

#list-row:selected {
    background-color: #89b4fa;
    color: #1e1e2e;
}

#list-row:hover {
    background-color: #504945;
}


`

var globalStyleProvider *gtk.CssProvider

func generateLauncherCSS(styling *config.StylingConfig) string {
	return fmt.Sprintf(`
#launcher-window {
    background-color: %s;
    color: %s;
    border-radius: %dpx;
    border: %dpx solid %s;
}

 #launcher-entry {
     background-color: %s;
     color: %s;
     padding: 12px;
     border: none;
     font-family: %s;
     font-size: %dpx;
     font-weight: %s;
 }

#launcher-entry:focus {
    border-bottom: %dpx solid %s;
}

#result-list {
    background-color: transparent;
}

 #list-row {
     padding: 4px 8px;
     border-bottom: %dpx solid %s;
     min-height: 32px;
     background-color: %s;
 }

#list-row:selected {
    background-color: %s;
    color: %s;
}

 #list-row:hover {
     background-color: %s;
 }

 #badges-box {
     background-color: #3c3836;
     padding: 4px 8px;
     border-radius: 3px;
     margin-top: 4px;
     font-size: 12px;
 }

 #badges-box label {
     color: #888888;
     font-family: %s;
     padding: 0px 4px;
 }

 #footer-box {
     background-color: #3c3836;
     padding: 4px 8px;
     border-radius: 3px;
     margin-top: 4px;
     font-size: 12px;
 }

 #footer-box label {
     color: #888888;
     font-family: %s;
 }


 `,
		styling.BackgroundColor,
		styling.ForegroundColor,
		styling.BorderRadius,
		styling.BorderWidth,
		styling.BorderColor,

		styling.EntryBackground,
		styling.ForegroundColor,
		styling.FontFamily,
		styling.FontSize,
		styling.FontWeight,

		styling.BorderWidth,
		styling.EntryFocusColor,

		styling.BorderWidth,
		styling.BorderColor,
		styling.ListRowBackground,

		styling.ListRowSelected,
		styling.BackgroundColor,

		styling.ListRowHover,

		styling.FontFamily,
		styling.FontFamily,
	)
}

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

	// Load user CSS file
	LoadCustomCSS()
}

func SetupLauncherStyles(cfg *config.Config) {
	screen, err := gdk.ScreenGetDefault()
	if err != nil || screen == nil {
		log.Printf("Warning: Failed to get default screen for launcher styles: %v", err)
		return
	}

	// Generate CSS from config
	launcherCSS := generateLauncherCSS(&cfg.Launcher.Styling)

	// Load built-in launcher CSS
	provider, _ := gtk.CssProviderNew()
	if err := provider.LoadFromData(launcherCSS); err != nil {
		log.Printf("Warning: Failed to load launcher styles: %v", err)
		return
	}

	gtk.AddProviderForScreen(screen, provider, gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
	log.Printf("Loaded launcher styles from config")
}

func LoadCustomCSS() {
	screen, err := gdk.ScreenGetDefault()
	if err != nil || screen == nil {
		return
	}

	home := os.Getenv("HOME")
	if home == "" {
		return
	}

	// Load launcher CSS
	launcherPath := home + "/.config/locus/launcher.css"
	if data, err := os.ReadFile(launcherPath); err == nil {
		provider, _ := gtk.CssProviderNew()
		if loadErr := provider.LoadFromData(string(data)); loadErr == nil {
			gtk.AddProviderForScreen(screen, provider, gtk.STYLE_PROVIDER_PRIORITY_USER)
			log.Printf("Loaded launcher CSS from %s", launcherPath)
		} else {
			log.Printf("Warning: Failed to load launcher CSS: %v", loadErr)
		}
	} else {
		log.Printf("Warning: Failed to read launcher CSS from %s: %v", launcherPath, err)
	}

	// Load statusbar CSS (legacy support)
	statusbarPath := home + "/.config/locus/statusbar.css"
	if data, err := os.ReadFile(statusbarPath); err == nil {
		provider, _ := gtk.CssProviderNew()
		if loadErr := provider.LoadFromData(string(data)); loadErr == nil {
			gtk.AddProviderForScreen(screen, provider, gtk.STYLE_PROVIDER_PRIORITY_USER)
			log.Printf("Loaded statusbar CSS from %s", statusbarPath)
		} else {
			log.Printf("Warning: Failed to load statusbar CSS: %v", loadErr)
		}
	}
}
