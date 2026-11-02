"""Image loading and caching utilities.

QML requests artwork through the ``image://nanoka`` provider, which calls
:func:`load_qt_image_sync` on the QML image thread.  Two caches sit in front of
the network:

* the memory cache, keyed by ``(url, (width, height))``, so scrolling back to a
  card does not read and decode the same payload again.  ``QImage`` is
  implicitly shared and only read here, so entries are safe to hand out from
  the image thread;
* the on-disk cache under ``CACHE_DIR/images``, written atomically, so a
  restart does not re-download the library.

A corrupt/truncated file in the disk cache is removed instead of being
decoded successfully-never and re-read on every launch.
"""

from __future__ import annotations

import hashlib
import logging
import math
import threading
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QSize, Qt
from PySide6.QtGui import QImage, QImageReader

from ..api.cache_io import write_bytes_atomic
from ..api.constants import CACHE_DIR
from ..api.http import get_session

logger = logging.getLogger(__name__)

IMAGE_CACHE_DIR = CACHE_DIR / "images"
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Rough ceiling for decoded images kept in memory.  QImage copies are
# implicitly shared, so evicting an entry only frees memory once QML drops its
# reference to the texture built from it.
IMAGE_CACHE_MAX_BYTES = 48 * 1024 * 1024

# Memory cache for loaded images: {(url, (w, h)): QImage}
IMAGE_CACHE: "OrderedDict[tuple[str, tuple[int, int] | None], QImage]" = OrderedDict()
_CACHE_BYTES = 0
_CACHE_LOCK = threading.Lock()

_REQUEST_TIMEOUT = (5, 20)

# Stable module-level name so tests can substitute the network boundary.
_get_session = get_session


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


def _cache_get(key) -> QImage | None:
    with _CACHE_LOCK:
        image = IMAGE_CACHE.get(key)
        if image is not None:
            IMAGE_CACHE.move_to_end(key)
        return image


def _image_bytes(image: QImage) -> int:
    return max(1, image.sizeInBytes())


def _cache_put(key, image: QImage):
    """Store *image* and evict the oldest entries over the memory budget."""
    global _CACHE_BYTES
    with _CACHE_LOCK:
        old = IMAGE_CACHE.pop(key, None)
        if old is not None:
            _CACHE_BYTES -= _image_bytes(old)
        IMAGE_CACHE[key] = image
        _CACHE_BYTES += _image_bytes(image)
        while _CACHE_BYTES > IMAGE_CACHE_MAX_BYTES and len(IMAGE_CACHE) > 1:
            _, evicted = IMAGE_CACHE.popitem(last=False)
            _CACHE_BYTES -= _image_bytes(evicted)
        _CACHE_BYTES = max(0, _CACHE_BYTES)


def _cache_clear():
    global _CACHE_BYTES
    with _CACHE_LOCK:
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
    try:
        write_bytes_atomic(cache_file, data)
    except Exception as exc:
        logger.error("Failed to save image to cache: %s", exc)


def _discard_cache_file(cache_file: Path, reason: str):
    try:
        cache_file.unlink(missing_ok=True)
        logger.warning("Discarded %s image cache entry %s", reason, cache_file)
    except OSError as exc:
        logger.error("Could not remove image cache file %s: %s", cache_file, exc)


def load_qt_image_sync(url, size=(100, 100)) -> QImage | None:
    """Load *url* at *size* from memory, the disk cache, or the network."""
    if not url:
        return None

    key = _key(url, size)
    cached = _cache_get(key)
    if cached is not None:
        return cached

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

    _cache_put(key, image)
    return image


def clear_image_cache():
    """Clear image cache (memory and disk)."""
    _cache_clear()
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
