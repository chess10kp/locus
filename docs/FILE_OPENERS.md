# File Opener Configuration

The file launcher uses a single command to open all file types.

## Usage

When using the file launcher (triggered by `file` or `f`), all files will be opened using the configured file opener.

## Configuration

The file opener is configured in your main `config.toml` file:

```toml
[file_search]
file_opener = "xdg-open"
```

### Common File Openers

- `xdg-open`: Uses the system's default application for each file type (recommended)
- `mimeo`: A smart file opener that uses mime types
- `handlr`: Alternative file opener using mime types
- `exo-open`: Xfce's default file opener
- Specific applications like `evince`, `feh`, `mpv`, etc. (will try to open all file types with that application)

### Examples

```toml
# Use xdg-open (system default - recommended)
[file_search]
file_opener = "xdg-open"

# Use mimeo
[file_search]
file_opener = "mimeo"

# Use handlr
[file_search]
file_opener = "handlr open"

# Use a specific application (not recommended - all files will try to open with it)
[file_search]
file_opener = "evince"
```

## Notes

- The file opener command is used for all file types
- For per-file-type configuration, use your system's default application settings or configure your chosen file opener
- The command must be in your `$PATH` or specified as a full path
- Most users should stick with `xdg-open` which respects system-wide file associations
