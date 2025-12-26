### Core Productivity Tools
- **Text Snippets**: Reusable text snippets for quick insertion

### Advanced Utilities
- **Flathub Integration**: Search and get the command to install applications
- **AUR Integration**: Search and get the command to install applications
- **Screen Recording**: Record screen or regions with obs-cli
- **Process Monitoring**: Top CPU and memory usage (topcpu/topmem)
- **Power Controls**: System power, session, and shutdown management
- **Windows Switching**: Switch between open windows
- **URL Plugin**: Pattern-matched direct URL opening
- **Accent Color Toggle**: Change system accent colors
- **Theme Switching**: Light/dark mode toggles

### UI and Services
- **OCR Integration**: Text recognition for images and screenshots
- **Thumbnail Generation**: Automatic thumbnail creation for images

### Extension Ecosystem
- **Well architectred python SDK for extensions**
- **Storage API**: Persistent storage for extensions
- **Extension Events**: Event system for extension lifecycle management

### UI and Interaction
- **Rich UI Components**: Toasts, confirm alerts, HUD notifications, navigation
- **Advanced Theming**: Dynamic light/dark theming with contrast adjustment
- **Fallback Commands**: Graceful degradation when actions fail

### Services and APIs
- **Comprehensive Window Management**: Full window bounds, focus, workspaces, screens
- **Advanced Clipboard (Wayland)**: Wayland-specific clipboard protocols
- **Application Management**: App listing, launching, URL handling
- **File Search API**: Dedicated advanced file search service
- **Multiple Calculator Backends**: Support for Qalculate! advanced calculator
- **Quick Link/Web Search**: Seamless web search integration

## Implementation Priority

### High Priority
- Notes, Todo, Snippets (core productivity)
- Bitwarden, Dictionary (security/productivity)
- Advanced Calculator, Flathub (utilities)
- Daemon IPC, Extension SDK (architecture)

### Medium Priority
- Window Management, Clipboard APIs (system integration)
- Rich UI Components, Theming (UI polish)
- OCR, Screen Recording (media features)

### Low Priority
- Raycast Compatibility, Extension Store (ecosystem)
- Power Controls, Theme Switching (niche features)


Multi-step navigation 	Show lists, let users drill down, navigate back
Rich cards 	Display markdown content (definitions, previews, help)
Preview panel 	Side panel with image/markdown/text preview, pinnable to screen
Multi-field forms 	Forms with text, textarea, select, checkbox fields
Image thumbnails 	Show image previews in result lists
Action buttons 	Add context actions per item (copy, delete, open folder)
Plugin action bar 	Toolbar buttons for plugin-level actions (Add, Wipe) with Ctrl+1-6 shortcuts
Confirmation dialogs 	Inline confirmation for dangerous actions (e.g., "Wipe All")
Image browser 	Full image browser UI with directory navigation
OCR text search 	Search images by text content (requires tesseract)
Execute commands 	Run any shell command, optionally save to history
Custom placeholders 	Change search bar placeholder text per step
Live search 	Filter results as user types
Submit mode 	Wait for Enter before processing (for text input, chat)
Auto-refresh polling 	Periodic updates for live data (process monitors, stats)
