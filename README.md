# Desktop Dashboard

A GTK4-based desktop dashboard and status bar built for Linux with Wayland/Hyprland support. This application provides a minimalistic overlay showing time, agenda, battery status, and workspace information.

## System Requirements & Assumptions

### Operating System
- **Linux only** - The application explicitly checks for Linux and will not work on other platforms
- **Wayland preferred** - Optimized for Wayland with GTK4 Layer Shell support
- **Hyprland window manager** - Specifically integrates with Hyprland for workspace information
- X11 fallback support is included but limited

### Dependencies
- **Python 3.13+** - Required Python version
- **GTK4** - GUI framework
- **GTK4 Layer Shell** - For Wayland overlay support (`libgtk4-layer-shell.so`)
- **PyGObject** - Python GTK bindings
- **System tools**:
  - `pgrep` - Process checking
  - `upower` - Battery information (fallback)
  - `hyprctl` - Hyprland control

### External Applications
- **Emacs with org-mode** - Required for agenda functionality
  - Must have Emacs server running
  - Requires `~/.emacs.d/init.el` configuration
  - Uses `org-agenda` for task management

### File System Assumptions
- **User home directory** - Application stores data in user's home
- **Cache directory** - `~/.cache/dashboard/` for habit tracking
- **Config files**:
  - `~/.time` - Time tracking counter
  - `~/.dashboard_tasks_visible` - Task visibility persistence
- **Battery paths** - Assumes `/sys/class/power_supply/BAT0` or similar
- **Hyprland environment** - Expects `HYPRLAND_INSTANCE_SIGNATURE` env var

### Hardware Assumptions
- **Battery present** - Laptop/notebook with battery monitoring
- **Multiple monitors** - Supports multi-monitor setups
- **Standard Linux filesystem** - Uses `/sys/` for system information

### Network Assumptions
- **Internet connection** - For weather data (python-weather API)
- **Weather API** - Uses OpenWeatherMap through python-weather library

## Installation

1. Install system dependencies:
```bash
# Ubuntu/Debian
sudo apt install python3.13 python3-pip libgtk-4-dev libgtk4-layer-shell-dev

# Arch Linux
sudo pacman -S python python-pip gtk4 gtk4-layer-shell
```

2. Install Python dependencies:
```bash
pip install -e .
# or
uv sync
```

3. Ensure Emacs server is running:
```bash
emacs --daemon
```

## Configuration

### Location
Edit `config.py` to change:
- `CITY` - Default city for weather (currently "detroit")

### Styling
Edit `style.py` to customize:
- Widget margins and padding
- Border styling
- Font sizes
- Calendar appearance

## Usage

### Main Dashboard
```bash
python main.py
```
- Shows current time with date tracking
- Displays Emacs org-agenda tasks
- Time tracking counter (clickable)
- Positioned at top-right of screen

### Status Bar
```bash
python status_bar.py
```
- Shows current time, battery status, and workspace
- Positioned at top-left of screen
- Updates in real-time

## Features

### Time Display
- Large clock with current time
- Date and day of week
- Year progress tracking (days, hours, minutes)
- Clickable counter for time tracking

### Agenda Integration
- Pulls tasks from Emacs org-agenda
- Toggle visibility with persistence
- Auto-refreshes every 30 seconds
- Scrollable task list

### System Monitoring
- Battery status with charging indicator
- Current Hyprland workspace
- Real-time updates

### Weather
- Temperature display for configured city
- Imperial units (Fahrenheit)

## Troubleshooting

### Common Issues

1. **"Layer shell not available"**
   - Install `gtk4-layer-shell`
   - Ensure running on Wayland
   - Falls back to regular window on X11

2. **"Emacs unavailable"**
   - Start Emacs server: `emacs --daemon`
   - Check `~/.emacs.d/init.el` exists
   - Ensure org-mode is configured

3. **"No Battery"**
   - Check battery path in `/sys/class/power_supply/`
   - Install `upower` for fallback support
   - May not work on desktop systems

4. **Weather not showing**
   - Check internet connection
   - Verify city name in config
   - API may be temporarily unavailable

### Debug Mode
The application includes extensive error handling and will print debug information to stdout when issues occur.

## Development

### Code Style
- Uses `# pyright:` and `# ruff: ignore` directives
- Type hints with `typing_extensions`
- Final classes where appropriate

### Architecture
- `main.py` - Main dashboard application
- `status_bar.py` - Status bar component
- `config.py` - Configuration variables
- `style.py` - Styling constants
- `weather.py` - Weather functionality
- `habits.py` - Habit tracking system
- `exceptions.py` - Custom exception classes

### Testing
No formal test suite currently included. Manual testing recommended.

## License

Add your license information here.