"""Image loading and caching utilities.

The loader is deliberately small, but a few invariants matter:

* Widgets are updated **on the GUI thread only**.  Decoding happens in the
  worker pool, and the image is handed back through a queued signal.
* The memory cache is keyed by ``(url, size)``.  The same artwork can be
  requested at different sizes (a 80x80 portrait in a card, a 18x18 icon in
  the same card) and each size must keep its own pixmap.
* The memory cache is bounded.  A cold cache plus hundreds of cards must not
  pin every decoded pixmap for the lifetime of the process.
* A corrupt/truncated file in the disk cache is removed instead of being
  decoded successfully-never and re-read on every launch.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from PySide6.QtCore import (
    QObject,
    Signal,
    QSize,
    QBuffer,
    QIODevice,
    Qt,
)
from PySide6.QtGui import QPixmap, QImage, QImageReader

logger = logging.getLogger(__name__)

IMAGE_CACHE_DIR = Path.home() / ".cache" / "nanoka_leaks" / "images"
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Rough ceiling for decoded pixmaps kept in memory.  QPixmap copies are
# implicitly shared, so evicting an entry only frees memory once no label
# references it anymore.
IMAGE_CACHE_MAX_BYTES = 48 * 1024 * 1024

# Memory cache for loaded images: {(url, (w, h)): QPixmap}
IMAGE_CACHE: "OrderedDict[tuple[str, tuple[int, int] | None], QPixmap]" = OrderedDict()
_CACHE_BYTES = 0

# Thread pool for background loading.  Small on purpose: the visible-first
# scheduling in GameSection means we never want to queue the whole library.
image_executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="nanoka-img")

_REQUEST_TIMEOUT = (5, 20)

# Don't hammer a missing asset on every reload; retry after this long.
FAILURE_TTL = 300.0
_FAILED: dict[tuple, float] = {}

_SESSION: requests.Session | None = None
_SESSION_LOCK = threading.Lock()
_DISK_LOCK = threading.Lock()


def _get_session() -> requests.Session:
    """Return the shared HTTP session (connection pooling for the workers)."""
    global _SESSION
    if _SESSION is None:
        with _SESSION_LOCK:
            if _SESSION is None:
                session = requests.Session()
                adapter = HTTPAdapter(
                    pool_connections=8,
                    pool_maxsize=16,
                    max_retries=1,
                )
                session.mount("https://", adapter)
                session.mount("http://", adapter)
                session.headers.setdefault(
                    "User-Agent", "NanokaLeaks/5.1 (+https://nanoka.cc)"
                )
                _SESSION = session
    return _SESSION


class _ImageLoaderSignals(QObject):
    """Signals for the asynchronous image loader (lives on the GUI thread)."""

    image_loaded = Signal(object, QImage)
    image_failed = Signal(object)

    def _dispatch(self, key, qimg):
        _handle_image_loaded(key, qimg)

    def _dispatch_failed(self, key):
        _handle_image_failed(key)


# Global signals instance, lazily created on the GUI thread.
_IMAGE_LOADER_SIGNALS: _ImageLoaderSignals | None = None


def get_signals() -> _ImageLoaderSignals:
    """Get or create the global signals instance."""
    global _IMAGE_LOADER_SIGNALS
    if _IMAGE_LOADER_SIGNALS is None:
        _IMAGE_LOADER_SIGNALS = _ImageLoaderSignals()
        # AutoConnection: direct on the GUI thread, queued from a worker.
        _IMAGE_LOADER_SIGNALS.image_loaded.connect(
            _IMAGE_LOADER_SIGNALS._dispatch
        )
        _IMAGE_LOADER_SIGNALS.image_failed.connect(
            _IMAGE_LOADER_SIGNALS._dispatch_failed
        )
    return _IMAGE_LOADER_SIGNALS


def _size_key(size) -> tuple[int, int] | None:
    """Normalise a requested size so it can be used as a cache key."""
    if not size:
        return None
    try:
        width, height = int(size[0]), int(size[1])
    except (TypeError, ValueError, IndexError):
        return None
    if width <= 0 or height <= 0:
        return None
    return (width, height)


def _key(url: str, size) -> tuple[str, tuple[int, int] | None]:
    return (url, _size_key(size))


def _cache_get(key) -> QPixmap | None:
    pixmap = IMAGE_CACHE.get(key)
    if pixmap is not None:
        IMAGE_CACHE.move_to_end(key)
    return pixmap


def _pixmap_bytes(pixmap: QPixmap) -> int:
    return max(1, pixmap.width() * pixmap.height() * 4)


def _cache_put(key, pixmap: QPixmap):
    """Store *pixmap* and evict the oldest entries over the memory budget."""
    global _CACHE_BYTES
    old = IMAGE_CACHE.pop(key, None)
    if old is not None:
        _CACHE_BYTES -= _pixmap_bytes(old)
    IMAGE_CACHE[key] = pixmap
    _CACHE_BYTES += _pixmap_bytes(pixmap)
    while _CACHE_BYTES > IMAGE_CACHE_MAX_BYTES and len(IMAGE_CACHE) > 1:
        _, evicted = IMAGE_CACHE.popitem(last=False)
        _CACHE_BYTES -= _pixmap_bytes(evicted)
    _CACHE_BYTES = max(0, _CACHE_BYTES)


def _cache_clear():
    global _CACHE_BYTES
    IMAGE_CACHE.clear()
    _CACHE_BYTES = 0


def _cover_size(source: QSize, target: tuple[int, int]) -> QSize:
    """Return the smallest size that covers *target* without distorting."""
    target_width, target_height = target
    if source.width() <= 0 or source.height() <= 0:
        return QSize(target_width, target_height)
    scale = max(
        target_width / source.width(),
        target_height / source.height(),
    )
    return QSize(
        max(target_width, math.ceil(source.width() * scale)),
        max(target_height, math.ceil(source.height() * scale)),
    )


def _crop_cover(image: QImage, target: tuple[int, int]) -> QImage:
    """Scale to cover *target*, centre horizontally and align to the top.

    Character faces sit near the top of the source artwork, so vertical
    centring crops away the part people actually want to see.
    """
    target_width, target_height = target
    if image.width() < target_width or image.height() < target_height:
        image = image.scaled(
            target_width,
            target_height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
    x = max(0, (image.width() - target_width) // 2)
    return image.copy(x, 0, target_width, target_height)


def _decode(data: bytes, size) -> QImage | None:
    """Decode image *data* into a QImage, cropped to *size* when given."""
    buf = QBuffer()
    buf.setData(data)
    buf.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buf)
    reader.setAutoTransform(True)
    size_key = _size_key(size)
    if size_key is not None:
        source_size = reader.size()
        if source_size.isValid() and not source_size.isEmpty():
            # Decode close to the final cover size instead of the full asset.
            reader.setScaledSize(_cover_size(source_size, size_key))
        else:
            reader.setScaledSize(QSize(*size_key))
    image = reader.read()
    if image.isNull():
        return None
    if size_key is not None:
        image = _crop_cover(image, size_key)
    return image


def _read_cache_file(cache_file: Path) -> bytes | None:
    try:
        return cache_file.read_bytes()
    except FileNotFoundError:
        return None
    except Exception as exc:  # pragma: no cover - unusual I/O failure
        logger.error("Failed to read cached image %s: %s", cache_file, exc)
        return None


def _write_cache_file(cache_file: Path, data: bytes):
    """Write atomically so a crash can never leave a half-written image."""
    temp_file = cache_file.with_name(f".{cache_file.name}.{os.getpid()}.tmp")
    try:
        with _DISK_LOCK:
            temp_file.write_bytes(data)
            os.replace(temp_file, cache_file)
    except Exception as exc:
        logger.error("Failed to save image to cache: %s", exc)
        try:
            temp_file.unlink(missing_ok=True)
        except OSError:
            pass


def _discard_cache_file(cache_file: Path, reason: str):
    try:
        cache_file.unlink(missing_ok=True)
        logger.warning("Discarded %s image cache entry %s", reason, cache_file)
    except OSError as exc:
        logger.error("Could not remove image cache file %s: %s", cache_file, exc)


def load_qt_image_sync(url, size=(100, 100)) -> QImage | None:
    """Synchronously load an image (used by the background thread)."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_file = IMAGE_CACHE_DIR / f"{url_hash}.png"

    data = _read_cache_file(cache_file)
    image = _decode(data, size) if data is not None else None
    if data is not None and image is None:
        # Corrupt or partially written payload: never trust it again.
        _discard_cache_file(cache_file, "corrupt")
        data = None

    if data is None:
        try:
            response = _get_session().get(url, timeout=_REQUEST_TIMEOUT)
            if response.status_code != 200:
                logger.error(
                    "Failed to load image %s (HTTP %s)", url, response.status_code
                )
                return None
            data = response.content
        except Exception as exc:
            logger.error("Failed to load image %s: %s", url, exc)
            return None

        image = _decode(data, size)
        if image is None:
            logger.error("Failed to decode image %s", url)
            return None
        _write_cache_file(cache_file, data)

    return image


def _background_load(signals: _ImageLoaderSignals, key, size):
    """Worker function for background loading."""
    url, _ = key
    qimg = load_qt_image_sync(url, size)
    if qimg is not None:
        # Queued back to the GUI thread by the signals object.
        signals.image_loaded.emit(key, qimg)
    else:
        signals.image_failed.emit(key)


class ImageRequest:
    """Handle returned by :func:`request_image` so callers can cancel it."""

    __slots__ = ("key", "callback", "cancelled")

    def __init__(self, key, callback):
        self.key = key
        self.callback = callback
        self.cancelled = False

    def cancel(self):
        """Drop this request's callback without affecting other requesters."""
        self.cancelled = True
        with _LOCK:
            callbacks = _CALLBACKS.get(self.key)
            if callbacks is None:
                return
            try:
                callbacks.remove(self)
            except ValueError:
                pass
            if not callbacks:
                _CALLBACKS.pop(self.key, None)


# Keep track of callbacks for pending requests: key -> list[ImageRequest]
_CALLBACKS: dict[tuple, list[ImageRequest]] = {}
_LOCK = threading.Lock()


def _handle_image_loaded(key, qimg):
    """Handle image loaded signal in the main thread."""
    _FAILED.pop(key, None)
    pixmap = QPixmap.fromImage(qimg)
    _cache_put(key, pixmap)

    with _LOCK:
        callbacks = _CALLBACKS.pop(key, [])

    for request in callbacks:
        if request.cancelled:
            continue
        try:
            request.callback(pixmap)
        except RuntimeError:
            # The widget was destroyed while the request was in flight.
            continue
        except Exception as exc:
            logger.error("Error in image callback for %s: %s", key[0], exc)


def _handle_image_failed(key):
    """Remember a failed asset so reloads do not hammer it immediately."""
    _FAILED[key] = time.monotonic()
    with _LOCK:
        _CALLBACKS.pop(key, None)
    logger.debug("Image request failed; suppressing retries for %ss: %s", FAILURE_TTL, key[0])


def request_image(url, callback, size=(100, 100)) -> ImageRequest | None:
    """Request an image asynchronously.

    If the (url, size) pair is cached, the callback is invoked immediately.
    Otherwise it is loaded in the background and invoked on the GUI thread
    when ready.  Returns a handle that can be cancelled.
    """
    if not url:
        return None

    # Ensure signals are initialized on the GUI thread before we submit.
    signals = get_signals()
    key = _key(url, size)

    pixmap = _cache_get(key)
    if pixmap is not None:
        try:
            callback(pixmap)
        except RuntimeError:
            pass  # The widget was destroyed before it could be updated.
        except Exception as exc:
            logger.error("Error in image callback for %s: %s", url, exc)
        return ImageRequest(key, callback)

    failed_at = _FAILED.get(key)
    if failed_at is not None:
        if time.monotonic() - failed_at < FAILURE_TTL:
            return None
        _FAILED.pop(key, None)

    request = ImageRequest(key, callback)
    with _LOCK:
        callbacks = _CALLBACKS.get(key)
        if callbacks is not None:
            callbacks.append(request)
            return request
        _CALLBACKS[key] = [request]

    image_executor.submit(_background_load, signals, key, _size_key(size))
    return request


def load_qt_image(url, size=(100, 100)):
    """Synchronous image loading (kept for compatibility).

    Prefer :func:`request_image` for UI code; it keeps the GUI responsive.
    """
    if not url:
        return None

    key = _key(url, size)
    pixmap = _cache_get(key)
    if pixmap is not None:
        return pixmap

    qimg = load_qt_image_sync(url, size)
    if qimg is not None:
        pixmap = QPixmap.fromImage(qimg)
        _cache_put(key, pixmap)
        return pixmap
    return None


def clear_image_cache():
    """Clear image cache (memory and disk)."""
    _cache_clear()
    _FAILED.clear()
    try:
        import shutil

        if IMAGE_CACHE_DIR.exists():
            for item in IMAGE_CACHE_DIR.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            logger.info("Image disk cache cleared")
    except Exception as exc:
        logger.error("Error clearing image disk cache: %s", exc)
