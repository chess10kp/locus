# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import os
import threading
import logging
from typing import Optional, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor
from gi.repository import GdkPixbuf, Gtk, Gio, GLib, Gdk

logger = logging.getLogger("IconManager")


class IconManager:
    """
    Centralized icon loading and caching system.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern for global icon manager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        from core.config import LAUNCHER_CONFIG

        # Load configuration
        self.config = LAUNCHER_CONFIG.get("icons", {})

        self.enable_icons = self.config.get("enable_icons", True)
        self.icon_size = self.config.get("icon_size", 32)
        self.cache_enabled = self.config.get("cache_icons", True)
        self.cache_size = self.config.get("cache_size", 200)
        self.fallback_icon = (
            self.config.get("fallback_icon", "image-missing") or "image-missing"
        )
        self.async_loading = self.config.get("async_loading", True)

        # Memory cache for loaded icons
        self._memory_cache: Dict[str, GdkPixbuf.Pixbuf] = {}
        self._cache_access_order: list = []  # For LRU eviction

        # Threading
        self.executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="IconLoader"
        )

        # Icon theme for theme icon resolution
        try:
            display = Gdk.Display.get_default()
            self.icon_theme = (
                Gtk.IconTheme.get_for_display(display) if display else None
            )
        except Exception as e:
            logger.error(f"Failed to get icon theme: {e}")
            self.icon_theme = None

        # MIME type mapping for file icons
        self.file_type_icons = {
            "text/plain": "text-x-generic",
            "text/markdown": "text-x-generic",
            "text/x-python": "text-x-python",
            "text/javascript": "text-x-javascript",
            "text/typescript": "text-x-typescript",
            "application/json": "text-x-json",
            "application/pdf": "application-pdf",
            "image/png": "image-x-generic",
            "image/jpeg": "image-x-generic",
            "image/gif": "image-x-generic",
            "image/svg+xml": "image-x-generic",
            "image/webp": "image-x-generic",
            "audio/mpeg": "audio-x-generic",
            "audio/flac": "audio-x-generic",
            "audio/wav": "audio-x-generic",
            "video/mp4": "video-x-generic",
            "video/webm": "video-x-generic",
            "application/zip": "application-x-zip",
            "application/x-tar": "application-x-tar",
            "application/gzip": "application-x-gzip",
        }

    def get_icon(
        self,
        icon_name: Optional[str] = None,
        file_path: Optional[str] = None,
        mime_type: Optional[str] = None,
        use_cache: Optional[bool] = None,
    ) -> Optional[GdkPixbuf.Pixbuf]:
        """
        Get icon as GdkPixbuf with caching and fallback handling.

        Args:
            icon_name: Icon name from theme or file path
            file_path: File path to get icon for (alternative to icon_name)
            mime_type: MIME type for file type icons
            use_cache: Override global cache setting for this call

        Returns:
            GdkPixbuf.Pixbuf or None if icon loading fails
        """

        if not self.enable_icons:
            return None

        # Use cache setting from param or config
        should_cache = use_cache if use_cache is not None else self.cache_enabled

        # Determine icon name
        if not icon_name:
            if file_path:
                icon_name = self._get_file_icon_name(file_path, mime_type)
            else:
                icon_name = self.fallback_icon

        if not icon_name:
            icon_name = self.fallback_icon

        # Check cache first
        cache_key = f"{icon_name}_{self.icon_size}"
        if should_cache and cache_key in self._memory_cache:
            self._update_cache_access_order(cache_key)
            return self._memory_cache[cache_key]
        else:
            pass

        # Load icon
        if not icon_name:
            icon_name = self.fallback_icon
        pixbuf = self._load_icon_sync(icon_name)

        if pixbuf:
            # Cache the result
            if should_cache:
                self._cache_icon(cache_key, pixbuf)
            return pixbuf

        return None

    def get_icon_async(
        self,
        icon_name: Optional[str] = None,
        file_path: Optional[str] = None,
        mime_type: Optional[str] = None,
        use_cache: Optional[bool] = None,
        callback: Optional[Callable] = None,
    ) -> None:
        """
        Load icon asynchronously with callback.

        Args:
            icon_name: Icon name from theme or file path
            file_path: File path to get icon for
            mime_type: MIME type for file type icons
            use_cache: Override global cache setting
            callback: Function to call with pixbuf result
        """
        if not callback:
            return

        # Check cache first on main thread
        should_cache = use_cache if use_cache is not None else self.cache_enabled
        cache_key = (
            f"{icon_name}_{self.icon_size}"
            if icon_name
            else f"{self.fallback_icon}_{self.icon_size}"
        )

        if should_cache and cache_key in self._memory_cache:
            self._update_cache_access_order(cache_key)
            callback(self._memory_cache[cache_key])
            return

        # Load in background thread
        future = self.executor.submit(
            self.get_icon, icon_name, file_path, mime_type, use_cache
        )

        # Schedule callback on main thread
        def check_callback():
            if future.done():
                try:
                    pixbuf = future.result()
                except Exception as e:
                    logger.error(f"Icon loading failed: {e}")
                    pixbuf = None
                GLib.idle_add(callback, pixbuf)
            else:
                # Check again in 10ms
                GLib.timeout_add(10, check_callback)

        GLib.timeout_add(10, check_callback)

    def clear_cache(self) -> None:
        """Clear the in-memory icon cache."""
        self._memory_cache.clear()
        self._cache_access_order.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get current cache statistics."""
        return {
            "cache_size": len(self._memory_cache),
            "max_cache_size": self.cache_size,
            "cache_enabled": self.cache_enabled,
            "icons_enabled": self.enable_icons,
            "icon_size": self.icon_size,
        }

    def _load_icon_sync(self, icon_name: str) -> Optional[GdkPixbuf.Pixbuf]:
        """Load icon synchronously with fallback handling."""
        if not icon_name:
            return None

        try:
            if self.icon_theme and self.icon_theme.has_icon(icon_name):
                return self._load_theme_icon(icon_name)

            # Try file path
            if os.path.isfile(icon_name):
                return self._load_file_icon(icon_name)

            # Try common icon variations
            variations = [
                icon_name,
            ]
            if icon_name:
                variations.extend(
                    [
                        icon_name.replace("_", "-"),
                        icon_name.replace("-", "_"),
                        f"{icon_name}-symbolic",
                        f"{icon_name}-symbolic",
                    ]
                )

            for variation in variations:
                if self.icon_theme and self.icon_theme.has_icon(variation):
                    return self._load_theme_icon(variation)

            # Try to load at common icon paths
            icon_paths = [
                f"/usr/share/icons/hicolor/{self.icon_size}x{self.icon_size}/apps/{icon_name}.png",
                f"/usr/share/icons/hicolor/{self.icon_size}x{self.icon_size}/apps/{icon_name}.svg",
                f"/usr/share/icons/hicolor/scalable/apps/{icon_name}.svg",
                f"/usr/share/pixmaps/{icon_name}.png",
                f"/usr/share/pixmaps/{icon_name}.svg",
                # AdwaitaLegacy paths
                f"/usr/share/icons/AdwaitaLegacy/{self.icon_size}x{self.icon_size}/legacy/{icon_name}.png",
                f"/usr/share/icons/AdwaitaLegacy/{self.icon_size}x{self.icon_size}/legacy/{icon_name}.svg",
                f"/usr/share/icons/AdwaitaLegacy/scalable/legacy/{icon_name}.svg",
            ]

            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    return self._load_file_icon(icon_path)

            return None

        except Exception as e:
            logger.error(f"Failed to load icon '{icon_name}': {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _load_theme_icon(self, icon_name: str) -> Optional[GdkPixbuf.Pixbuf]:
        """Load icon from GTK theme."""

        if not self.icon_theme:
            return None

        try:
            icon_paintable = self.icon_theme.lookup_icon(
                icon_name, None, self.icon_size, 1, Gtk.TextDirection.NONE, 0
            )

            if icon_paintable:
                # Try to get the file path from the icon paintable
                # Some GTK4 implementations support getting the file
                if hasattr(icon_paintable, "get_file"):
                    icon_file = icon_paintable.get_file()
                    if icon_file:
                        file_path = icon_file.get_path()
                        if file_path and os.path.exists(file_path):
                            return self._load_file_icon(file_path)

                # Fallback: try to load at common icon paths
                icon_paths = [
                    f"/usr/share/icons/hicolor/{self.icon_size}x{self.icon_size}/apps/{icon_name}.png",
                    f"/usr/share/icons/hicolor/{self.icon_size}x{self.icon_size}/apps/{icon_name}.svg",
                    f"/usr/share/icons/hicolor/scalable/apps/{icon_name}.svg",
                    f"/usr/share/pixmaps/{icon_name}.png",
                    f"/usr/share/pixmaps/{icon_name}.svg",
                    # AdwaitaLegacy paths (common on many systems)
                    f"/usr/share/icons/AdwaitaLegacy/{self.icon_size}x{self.icon_size}/legacy/{icon_name}.png",
                    f"/usr/share/icons/AdwaitaLegacy/{self.icon_size}x{self.icon_size}/legacy/{icon_name}.svg",
                    f"/usr/share/icons/AdwaitaLegacy/scalable/legacy/{icon_name}.svg",
                ]

                for icon_path in icon_paths:
                    if os.path.exists(icon_path):
                        return self._load_file_icon(icon_path)

        except Exception as e:
            logger.error(f"Failed to load theme icon '{icon_name}': {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")

        return None

    def _load_file_icon(self, file_path: str) -> Optional[GdkPixbuf.Pixbuf]:
        """Load icon from file path."""

        try:
            if not os.path.exists(file_path):
                return None

            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                file_path, self.icon_size, self.icon_size
            )
            return pixbuf
        except Exception as e:
            logger.error(f"Failed to load file icon '{file_path}': {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _get_file_icon_name(
        self, file_path: str, mime_type: Optional[str] = None
    ) -> Optional[str]:
        """Get appropriate icon name for a file."""
        if mime_type:
            return self.file_type_icons.get(mime_type, self.fallback_icon)

        # Try to determine MIME type from file
        try:
            content_type = Gio.content_type_guess(file_path, None)[0]
            if content_type:
                return self.file_type_icons.get(content_type, self.fallback_icon)
        except Exception:
            pass

        return self.fallback_icon

    def _cache_icon(self, key: str, pixbuf: GdkPixbuf.Pixbuf) -> None:
        """Cache an icon in memory."""
        if len(self._memory_cache) >= self.cache_size:
            # Evict least recently used
            oldest_key = self._cache_access_order.pop(0)
            del self._memory_cache[oldest_key]

        self._memory_cache[key] = pixbuf
        self._cache_access_order.append(key)

    def _update_cache_access_order(self, key: str) -> None:
        """Update LRU access order for cache."""
        if key in self._cache_access_order:
            self._cache_access_order.remove(key)
        self._cache_access_order.append(key)


icon_manager = IconManager()
