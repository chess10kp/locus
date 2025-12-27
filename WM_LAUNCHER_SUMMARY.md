# WM Launcher Summary

## Changes Made

1. **Replaced sway_launcher.py with wm_launcher.py**
   - Changed command trigger from "sway" to "wm" 
   - Added support for both scrollwm and sway window managers
   - Uses scrollmsg when available, falls back to swaymsg

2. **Updated Registration**
   - Modified `core/launcher_window.py` to import and register WMLauncher instead of SwayLauncher

3. **Enhanced Command Set**
   - All original 58 i3/sway commands preserved
   - Added 10 scrollwm-specific commands:
     - `toggle overview` - Toggle overview mode
     - `enable/disable animations` - Animation controls
     - `reset alignment` - Reset window alignment
     - `jump mode` - Enter jump navigation mode
     - `cycle size` - Cycle window sizes
     - `set size small/medium/large` - Set specific window sizes
     - `fit size` - Fit window to content

## Usage

**Trigger:** `>wm`

**Examples:**
- `>wm` - Browse all available commands
- `>wm toggle floating` - Toggle floating mode
- `>wm workspace 3` - Switch to workspace 3
- `>wm toggle overview` - Toggle scrollwm overview mode
- `>wm custom command` - Execute any valid i3/sway/scroll command

## Window Manager Compatibility

The launcher automatically detects and uses:
1. **scrollwm** (via scrollmsg) - Primary support
2. **sway** (via swaymsg) - Fallback support
3. **i3** (via i3-msg) - Basic compatibility (not tested)

## Total Commands: 68

**Window Management:** 14 commands
**Workspace Navigation:** 37 commands  
**Window Groups/Tabs:** 6 commands
**Scrollwm-specific:** 10 commands

The launcher is now ready for use with scrollwm or sway!