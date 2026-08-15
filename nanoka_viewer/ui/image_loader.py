"""Image loading and caching utilities."""

import hashlib
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PySide6.QtCore import QObject, Signal, QCoreApplication, Qt, QSize, QBuffer, QIODevice
from PySide6.QtGui import QPixmap, QImage, QImageReader

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

    data = None
    if cache_file.exists():
        try:
            data = cache_file.read_bytes()
        except Exception as e:
            logger.error(f"Failed to read cached image {cache_file}: {e}")

    if data is None:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.content
                try:
                    cache_file.write_bytes(data)
                except Exception as e:
                    logger.error(f"Failed to save image to cache: {e}")
        except Exception as e:
            logger.error(f"Failed to load image {url}: {e}")
            return None

    qimg = None
    if data is not None:
        buf = QBuffer()
        buf.setData(data)
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        reader = QImageReader(buf)
        reader.setAutoTransform(True)
        reader.setScaledSize(QSize(size[0], size[1]))
        qimg = reader.read()
    if qimg is None:
        logger.error(f"Failed to decode image {url}")
    return qimg


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


def clear_image_cache():
    """Clear image cache (memory and disk)."""
    global IMAGE_CACHE
    IMAGE_CACHE = {}
    try:
        import shutil

        if IMAGE_CACHE_DIR.exists():
            # Use shutil.rmtree to clear everything in the directory
            for item in IMAGE_CACHE_DIR.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            logger.info("Image disk cache cleared")
    except Exception as e:
        logger.error(f"Error clearing image disk cache: {e}")
