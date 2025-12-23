# Grid View API for Custom Launchers

This document describes the new grid view API that allows custom launchers to display results in a grid layout with optional metadata.

## Overview

The grid view API enables custom launchers to:
- Display results in a configurable grid layout instead of a vertical list
- Show optional metadata alongside or over items
- Customize grid dimensions, item sizes, and spacing
- Control image aspect ratios and metadata positioning

## API Components

### 1. LauncherSizeMode.GRID

A new size mode that enables grid layout:

```python
from core.launcher_registry import LauncherSizeMode

def get_size_mode(self) -> tuple[LauncherSizeMode, Optional[tuple[int, int]]]:
    return LauncherSizeMode.GRID, (1200, 800)  # Optional custom size
```

### 2. get_grid_config() Method

Configure the grid layout and behavior:

```python
def get_grid_config(self) -> Dict[str, Any]:
    return {
        'columns': 4,              # Number of grid columns
        'item_width': 250,          # Width of each grid item
        'item_height': 200,         # Height of each grid item
        'spacing': 10,              # Spacing between items
        'show_metadata': True,       # Whether to show text metadata
        'metadata_position': 'bottom', # Where to show metadata: 'bottom', 'overlay', 'hidden'
        'aspect_ratio': 'original'    # How to handle aspect ratios: 'square', 'original', 'fixed'
    }
```

### 3. GridSearchResult Class

Create grid items with rich metadata:

```python
from core.search_models import GridSearchResult

# Basic grid item with title and image
result = GridSearchResult(
    title="My Image",
    image_path="/path/to/image.jpg",
    metadata={'size': '2.1MB', 'date': '2024-01-15'},
    index=1  # For Alt+number shortcuts
)
```

### 4. add_grid_result() Method

Add grid results to the launcher:

```python
# In your launcher's populate() method
launcher_core.add_grid_result(
    title="Sunset Photo",
    image_path="/path/to/sunset.jpg",
    metadata={'size': '2.1MB', 'date': '2024-01-15', 'type': 'JPEG'},
    index=i+1  # Alt+1-9 shortcuts
)
```

## Configuration Options

### Grid Layout

- `columns`: Number of columns in the grid (default: 4)
- `item_width`: Width of each grid item in pixels (default: 200)
- `item_height`: Height of each grid item in pixels (default: 200)
- `spacing`: Spacing between items in pixels (default: 10)

### Metadata Display

- `show_metadata`: Whether to show text metadata (default: True)
- `metadata_position`: Where to place metadata
  - `'bottom'`: Below the image (recommended)
  - `'overlay'`: Overlaid on the image
  - `'hidden'`: No text metadata shown
- `aspect_ratio`: How to handle image aspect ratios
  - `'square'`: Force square aspect ratio
  - `'original'`: Preserve original aspect ratio (recommended)
  - `'fixed'`: Use exact dimensions, may stretch images

## Example Implementation

See `launchers/gallery_launcher.py` for a complete example:

```python
class GalleryLauncher(LauncherInterface):
    @property
    def command_triggers(self) -> List[str]:
        return [">gallery", ">images"]

    def get_size_mode(self) -> tuple[LauncherSizeMode, Optional[tuple[int, int]]]:
        return LauncherSizeMode.GRID, (1200, 800)

    def get_grid_config(self) -> Dict[str, Any]:
        return {
            'columns': 4,
            'item_width': 250,
            'item_height': 200,
            'spacing': 10,
            'show_metadata': True,
            'metadata_position': 'bottom',
            'aspect_ratio': 'original'
        }

    def populate(self, query: str, launcher_core) -> None:
        # Your launcher logic here
        for item in search_results:
            launcher_core.add_grid_result(
                title=item['title'],
                image_path=item['path'],
                metadata=item['metadata'],
                index=i+1
            )
```

## Usage

Once implemented, users can access your grid launcher with:
- `>gallery` or `>images` (your configured triggers)
- Arrow keys for navigation
- Alt+1-9 for quick selection
- Click to select items
- Custom metadata display based on configuration

## Integration Notes

- Grid mode automatically calculates optimal window size based on configuration
- Image loading includes error handling and fallback placeholders
- Metadata formatting is compact to fit grid items
- All existing launcher features (hooks, tab completion, etc.) work with grid mode
- Performance considerations: limit results for better responsiveness