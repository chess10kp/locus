# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

"""Clipboard backend for Linux (X11/Wayland)."""

import subprocess
from typing import Optional
from enum import Enum

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk, GLib


class ClipboardBackend(Enum):
    """Available clipboard backends."""

    GTK = "gtk"  # Use GTK clipboard (works on both X11 and Wayland)
    WL_CLIPBOARD = "wl-clipboard"  # Use wl-clipboard (Wayland only)
    XSEL = "xsel"  # Use xsel (X11 only)
    XCLIP = "xclip"  # Use xclip (X11 only)


class ClipboardManager:
    """Manager for clipboard operations on Linux."""

    def __init__(self, backend: ClipboardBackend = ClipboardBackend.GTK):
        """Initialize the clipboard manager.

        Args:
            backend: The clipboard backend to use
        """
        self.backend = backend
        self._display = None  # For GTK clipboard

    def copy(self, text: str) -> bool:
        """Copy text to clipboard.

        Args:
            text: The text to copy

        Returns:
            True if successful, False otherwise
        """
        if not text:
            return False

        if self.backend == ClipboardBackend.GTK:
            return self._copy_gtk(text)
        elif self.backend == ClipboardBackend.WL_CLIPBOARD:
            return self._copy_wl_clipboard(text)
        elif self.backend == ClipboardBackend.XSEL:
            return self._copy_xsel(text)
        elif self.backend == ClipboardBackend.XCLIP:
            return self._copy_xclip(text)
        else:
            return False

    def paste(self) -> Optional[str]:
        """Paste text from clipboard.

        Returns:
            The clipboard contents, or None if unavailable
        """
        if self.backend == ClipboardBackend.GTK:
            return self._paste_gtk()
        elif self.backend == ClipboardBackend.WL_CLIPBOARD:
            return self._paste_wl_clipboard()
        elif self.backend == ClipboardBackend.XSEL:
            return self._paste_xsel()
        elif self.backend == ClipboardBackend.XCLIP:
            return self._paste_xclip()
        else:
            return None

    def _copy_gtk(self, text: str) -> bool:
        """Copy using GTK clipboard.

        GTK clipboard works on both X11 and Wayland and is the most reliable method.
        """
        try:
            # Get the default display
            display = Gdk.Display.get_default()
            if not display:
                return False

            # Get the clipboard
            clipboard = Gdk.Display.get_clipboard(display)

            # Convert text to GLib.Bytes
            bytes_data = GLib.Bytes.new(text.encode("utf-8"))

            # Set the clipboard content
            clipboard.set_content(Gdk.ContentProvider.new_for_bytes(
                "text/plain;charset=utf-8",
                bytes_data
            ))

            # Store the text for immediate retrieval
            self._last_copied = text
            return True

        except Exception as e:
            print(f"Error copying with GTK clipboard: {e}")
            return False

    def _paste_gtk(self) -> Optional[str]:
        """Paste using GTK clipboard."""
        try:
            display = Gdk.Display.get_default()
            if not display:
                return None

            clipboard = Gdk.Display.get_clipboard(display)

            # Note: GTK4 clipboard is async, so we return the last copied text
            # For async paste, you would need to use callbacks
            return getattr(self, "_last_copied", None)

        except Exception as e:
            print(f"Error pasting with GTK clipboard: {e}")
            return None

    def _copy_wl_clipboard(self, text: str) -> bool:
        """Copy using wl-clipboard (Wayland)."""
        try:
            result = subprocess.run(
                ["wl-copy"],
                input=text,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except FileNotFoundError:
            print("wl-copy not found. Install wl-clipboard for Wayland support.")
            return False
        except Exception as e:
            print(f"Error copying with wl-copy: {e}")
            return False

    def _paste_wl_clipboard(self) -> Optional[str]:
        """Paste using wl-clipboard (Wayland)."""
        try:
            result = subprocess.run(
                ["wl-paste", "--no-newline"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"Error pasting with wl-paste: {e}")
            return None

    def _copy_xsel(self, text: str) -> bool:
        """Copy using xsel (X11)."""
        try:
            result = subprocess.run(
                ["xsel", "--input", "--clipboard"],
                input=text,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except FileNotFoundError:
            print("xsel not found. Install xsel for X11 clipboard support.")
            return False
        except Exception as e:
            print(f"Error copying with xsel: {e}")
            return False

    def _paste_xsel(self) -> Optional[str]:
        """Paste using xsel (X11)."""
        try:
            result = subprocess.run(
                ["xsel", "--output", "--clipboard"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"Error pasting with xsel: {e}")
            return None

    def _copy_xclip(self, text: str) -> bool:
        """Copy using xclip (X11)."""
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except FileNotFoundError:
            print("xclip not found. Install xclip for X11 clipboard support.")
            return False
        except Exception as e:
            print(f"Error copying with xclip: {e}")
            return False

    def _paste_xclip(self) -> Optional[str]:
        """Paste using xclip (X11)."""
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"Error pasting with xclip: {e}")
            return None


# Singleton instance
_clipboard_manager: Optional[ClipboardManager] = None


def get_clipboard() -> ClipboardManager:
    """Get the singleton clipboard manager instance.

    Returns:
        The clipboard manager instance
    """
    global _clipboard_manager
    if _clipboard_manager is None:
        _clipboard_manager = ClipboardManager(backend=ClipboardBackend.GTK)
    return _clipboard_manager


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard.

    Args:
        text: The text to copy

    Returns:
        True if successful, False otherwise
    """
    return get_clipboard().copy(text)


def paste_from_clipboard() -> Optional[str]:
    """Paste text from clipboard.

    Returns:
        The clipboard contents, or None if unavailable
    """
    return get_clipboard().paste()
