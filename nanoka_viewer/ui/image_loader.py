"""Image loading and caching utilities."""

import hashlib
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image
from PySide6.QtCore import QObject, Signal, QCoreApplication
from PySide6.QtGui import QPixmap, QImage

logger = logging.getLogger(__name__)

IMAGE_CACHE_DIR = Path.home() / ".cache" / "nanoka_leaks" / "images"
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Memory cache for loaded images
IMAGE_CACHE = {}

# Thread pool for background loading
image_executor = ThreadPoolExecutor(max_workers=8)


class ImageLoaderSignal(QObject):
    """Signals for the asynchronous image loader."""

    image_loaded = Signal(str, QImage)


# Global signals instance, lazily created
_IMAGE_LOADER_SIGNALS = None


def get_signals():
    """Get or create the global signals instance."""
    global _IMAGE_LOADER_SIGNALS
    if _IMAGE_LOADER_SIGNALS is None:
        _IMAGE_LOADER_SIGNALS = ImageLoaderSignal()
        _IMAGE_LOADER_SIGNALS.image_loaded.connect(_handle_image_loaded)
    return _IMAGE_LOADER_SIGNALS


def load_qt_image_sync(url, size=(100, 100)):
    """Synchronously load an image (used by the background thread)."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_file = IMAGE_CACHE_DIR / f"{url_hash}.png"

    img = None
    if cache_file.exists():
        try:
            img = Image.open(cache_file).convert("RGBA")
        except Exception as e:
            logger.error(f"Failed to load cached image {cache_file}: {e}")

    if img is None:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content)).convert("RGBA")
                try:
                    img.save(cache_file, "PNG")
                except Exception as e:
                    logger.error(f"Failed to save image to cache: {e}")
        except Exception as e:
            logger.error(f"Failed to load image {url}: {e}")
            return None

    if img:
        img = img.resize(size, Image.Resampling.LANCZOS)
        # Create QImage which is thread-safe
        data = img.tobytes("raw", "RGBA")
        qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
        # Return a copy to ensure memory safety across threads
        return qimg.copy()
    return None


def _background_load(url, size):
    """Worker function for background loading."""
    qimg = load_qt_image_sync(url, size)
    if qimg:
        get_signals().image_loaded.emit(url, qimg)


# Keep track of callbacks for pending requests
_CALLBACKS = {}  # url -> list of callbacks
_LOCK = threading.Lock()


def _handle_image_loaded(url, qimg):
    """Handle image loaded signal in the main thread."""
    pixmap = QPixmap.fromImage(qimg)
    IMAGE_CACHE[url] = pixmap

    with _LOCK:
        callbacks = _CALLBACKS.pop(url, [])

    for callback in callbacks:
        try:
            callback(pixmap)
        except Exception as e:
            logger.error(f"Error in image callback for {url}: {e}")


def request_image(url, callback, size=(100, 100)):
    """
    Request an image asynchronously.
    If cached, the callback is called immediately.
    Otherwise, it's loaded in the background and the callback is called when ready.
    """
    if not url:
        return

    # Ensure signals are initialized (should happen in main thread)
    get_signals()

    # Check memory cache
    if url in IMAGE_CACHE:
        callback(IMAGE_CACHE[url])
        return

    with _LOCK:
        if url in _CALLBACKS:
            _CALLBACKS[url].append(callback)
            return
        _CALLBACKS[url] = [callback]

    # Submit to thread pool
    image_executor.submit(_background_load, url, size)


def load_qt_image(url, size=(100, 100)):
    """
    Deprecated: Synchronous image loading.
    Use request_image for better responsiveness.
    """
    if not url:
        return None

    if url in IMAGE_CACHE:
        return IMAGE_CACHE[url]

    qimg = load_qt_image_sync(url, size)
    if qimg:
        pixmap = QPixmap.fromImage(qimg)
        IMAGE_CACHE[url] = pixmap
        return pixmap
    return None
