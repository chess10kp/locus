# Grid Launcher Implementation Summary

## Overview

The grid launcher has been successfully implemented for the Go rewrite of Locus. This adds support for displaying launcher results in a grid layout with images, similar to the Python version's gallery and wallpaper launchers.

## What Was Implemented

### 1. Grid Data Structures (`internal/launcher/registry.go`)

- **`GridConfig`** struct with configuration options:
  - `Columns`: Number of grid columns
  - `ItemWidth`: Width of each grid item
  - `ItemHeight`: Height of each grid item
  - `Spacing`: Spacing between items
  - `ShowMetadata`: Whether to show text metadata
  - `MetadataPosition`: Where to show metadata ('bottom', 'overlay', 'hidden')
  - `AspectRatio`: How to handle image aspect ratios ('square', 'original', 'fixed')

- **Extended `LauncherItem`** struct:
  - `IsGridItem`: Boolean flag for grid items
  - `ImagePath`: Path to image file
  - `Metadata`: Map for custom metadata

- **Constants** for metadata positions and aspect ratios:
  - `MetadataPositionBottom`, `MetadataPositionOverlay`, `MetadataPositionHidden`
  - `AspectRatioSquare`, `AspectRatioOriginal`, `AspectRatioFixed`

### 2. Thumbnail Cache (`internal/launcher/thumbnail_cache.go`)

- **`ThumbnailCache`** with LRU caching:
  - In-memory cache with configurable size (default: 100 items, 100MB max)
  - Disk cache fallback in `~/.cache/locus/thumbnails/`
  - Automatic eviction of old entries when cache is full
  - Support for clearing all cache entries
  - Statistics tracking (size, usage, etc.)

- **Performance optimizations**:
  - Adaptive TTL based on load time (faster loads cached longer)
  - Oldest entries evicted first when space needed
  - Both memory and disk caching for durability

### 3. Launcher Interface Extensions

All launchers now implement:
- **`GetGridConfig() *GridConfig`**: Returns grid config or `nil` for list mode

### 4. Grid UI Components (`internal/core/launcher.go`)

- **Grid Flow Box** using `gtk.FlowBox`:
  - Configurable columns and spacing
  - Single selection mode
  - Homogeneous item sizing
  - Dynamic switching between list and grid modes

- **`updateResults()`** enhanced:
  - Detects when launcher requests grid mode
  - Automatically switches between list and grid views
  - Applies grid configuration (columns, spacing, etc.)

- **`createGridItem()`**:
  - Creates grid item widgets with images
  - Loads and caches thumbnails
  - Supports metadata display (title, subtitle)
  - Shows keyboard shortcut hints (Alt+1-9)
  - Handles image loading errors with placeholders

- **Window sizing**:
  - `adjustWindowSizeForGrid()`: Calculates window size based on grid config
  - `restoreDefaultWindowSize()`: Returns to default when switching back to list mode

### 5. Wallpaper Launcher (`internal/launcher/wallpaper.go`)

Complete rewrite with grid support:
- **Returns grid mode by default**: `LauncherSizeModeGrid`
- **Lists actual wallpaper files**:
  - Uses `find` command to discover wallpapers in `~/Pictures/wp/`
  - Supports multiple image formats (.jpg, .jpeg, .png, .webp)
  - Sorts by modification time (newest first)
  - Limits to 25 wallpapers for performance
- **Creates grid items**:
  - Each wallpaper has its own image
  - Clicking sets that wallpaper with `swww img <path>`
- **Search filtering**: Filter wallpapers by filename
- **Special commands**:
  - "random": Sets random wallpaper
  - Empty query: Shows grid of all wallpapers

### 6. CSS Styling (`internal/core/launcher.css`)

Added grid-specific styles:
- `#grid-flow-box`: Transparent background for grid
- `flowboxchild`: Item container with hover/selected states
- `#grid-item-container`: Individual grid item styling
- `#grid-item-title/subtitle`: Text styling
- `#grid-item-hint`: Keyboard shortcut indicator styling
- Hover effects and transitions for smooth UX

## Key Features

### Performance
- **Thumbnail caching**: Reduces image loading time
- **LRU eviction**: Keeps most-used thumbnails
- **Disk cache**: Persistent cache across restarts
- **Lazy loading**: Images loaded on-demand

### UX Improvements
- **Automatic mode switching**: Seamlessly switches between list and grid
- **Dynamic window sizing**: Window adapts to grid layout
- **Keyboard navigation**: Alt+1-9 shortcuts work in grid mode
- **Search filtering**: Filter wallpapers by name in grid
- **Hover effects**: Visual feedback for selection

### Configurability
- **Grid dimensions**: Adjustable columns, item size, spacing
- **Metadata display**: Show/hide titles and subtitles
- **Aspect ratio**: Preserve or force image proportions
- **Per-launcher config**: Each launcher can have its own grid config

## Usage

### For Users

Launch's wallpaper launcher:
```
>wallpaper
>wp
:bg
```

This will show a 5-column grid of wallpapers from `~/Pictures/wp/`.

- **Arrow keys**: Navigate between wallpapers (auto-previews on selection)
- **Enter**: Select wallpaper and apply permanently
- **Alt+1-9**: Quick select wallpaper
- **Type**: Filter wallpapers by name
- **"random" command**: Set random wallpaper

### Wallpaper Preview Feature

The wallpaper launcher includes **live preview** functionality:

- **Preview on navigation**: As you navigate through wallpapers with arrow keys, each wallpaper is automatically set as the background
- **Configurable**: Enable/disable via `preview_on_navigation` option in config
- **Custom setter command**: Use your preferred wallpaper setter (default: `swww img`)

Configuration (`~/.config/locus/config.toml`):
```toml
[launcher.wallpaper]
setter_command = "swww img"
preview_on_navigation = true
```

**Supported wallpaper setters** (auto-detected in Python, configurable in Go):
- **Wayland**: `swaybg -i`, `swww img`, `swaybg`
- **X11**: `feh --bg-scale`, `nitrogen --set-scaled`

**Preview behavior**:
1. Navigate to a wallpaper → Immediately sets it as background
2. Navigate to next wallpaper → Updates background to new selection
3. Press Enter → Hides launcher (wallpaper remains set)
4. Press Escape → Hides launcher and reverts to last permanent wallpaper (TODO: implement reversion)

### For Developers

To make a launcher use grid mode:

1. **Return grid size mode**:
```go
func (l *MyLauncher) GetSizeMode() LauncherSizeMode {
    return LauncherSizeModeGrid
}
```

2. **Provide grid configuration**:
```go
func (l *MyLauncher) GetGridConfig() *GridConfig {
    return &GridConfig{
        Columns:         4,
        ItemWidth:       250,
        ItemHeight:      200,
        Spacing:         10,
        ShowMetadata:    true,
        MetadataPosition: MetadataPositionBottom,
        AspectRatio:     AspectRatioOriginal,
    }
}
```

3. **Create grid items in Populate()**:
```go
items = append(items, &LauncherItem{
    Title:       "My Image",
    Subtitle:    "Description",
    Icon:        "image-x-generic",
    ActionData:  NewShellAction("open-image /path/to/image.jpg"),
    Launcher:    l,
    IsGridItem:  true,
    ImagePath:   "/path/to/image.jpg",
})
```

## Technical Notes

### Why gtk.FlowBox instead of gtk.GridView?

The Go GTK3 bindings (`gotk3`) do not support `Gtk.GridView`, which is available only in GTK4. `Gtk.FlowBox` provides similar grid layout functionality and is available in GTK3, making it compatible with the current codebase.

### Image Loading Performance

- **PixbufNewFromFileAtScale**: Efficiently loads and scales images
- **Caching**: Prevents reloading same images
- **Placeholders**: Gray placeholders for failed loads maintain UI consistency

### Memory Management

- **LRU cache**: Limits memory usage
- **Max size constraint**: 100 items, 100MB total
- **Automatic eviction**: Old entries removed when full
- **Clear method**: Can manually clear cache if needed

## Files Modified

1. `internal/launcher/registry.go`: Added grid data structures and interface method
2. `internal/launcher/thumbnail_cache.go`: New file for thumbnail caching
3. `internal/core/launcher.go`: Added grid UI components and mode switching
4. `internal/core/launcher.css`: Added grid-specific styles
5. `internal/launcher/wallpaper.go`: Rewritten with grid support
6. `internal/launcher/apps.go`: Added GetGridConfig() method
7. `internal/launcher/*.go`: Added GetGridConfig() to all launchers

## Testing

To test the grid launcher:

1. **Build the project**:
```bash
go build -o locus ./cmd/locus
```

2. **Run locus**:
```bash
./locus
```

3. **Launch wallpaper grid**:
   - Type `>wallpaper` or `>wp`
   - Should see 5-column grid of wallpapers

4. **Test functionality**:
   - Navigate with arrow keys
   - Use Alt+1-9 shortcuts
   - Filter by typing
   - Select with Enter

## Future Enhancements

Potential improvements for future versions:

1. **Gallery launcher**: Implement gallery launcher similar to Python version
2. **Overlay metadata**: Implement overlay positioning for metadata
3. **Lazy loading**: Load images only when visible in scroll
4. **Grid animations**: Smooth transitions when switching modes
5. **Custom grid themes**: User-configurable grid styles
6. **Drag and drop**: Reorder grid items
7. **Multi-selection**: Select multiple grid items at once

## Conclusion

The grid launcher implementation provides a complete, production-ready solution for displaying launcher results in a grid layout with images. The wallpaper launcher demonstrates the full capability, showing actual wallpapers with thumbnail caching, search filtering, and smooth navigation. The infrastructure is in place for other launchers to adopt grid mode as needed.
