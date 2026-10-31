"""Image provider that serves card artwork to QML.

QML asks for ``image://nanoka/?url=<percent-encoded>&w=80&h=80``.  The
provider is flagged ``ForceAsynchronousImageLoading``, so ``requestImage``
runs on the QML image thread and never blocks the GUI while a portrait is
downloaded or decoded.

It delegates to :func:`nanoka_viewer.ui.image_loader.load_qt_image_sync`, the
same disk/network cache the widget UI used, so switching to QML does not add
a second download path or a second copy of the cache.
"""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QSize, QUrl
from PySide6.QtGui import QImage
from PySide6.QtQml import QQmlImageProviderBase
from PySide6.QtQuick import QQuickImageProvider

from .image_loader import load_qt_image_sync

logger = logging.getLogger(__name__)

PROVIDER_ID = "nanoka"

# Second provider, used by the details popup: artwork arrives as raw bytes from
# its own cache/download path, so it is registered under a token instead of a
# URL.
ART_PROVIDER_ID = "nanokaart"

# Used when a request omits (or corrupts) its size parameters.
DEFAULT_SIZE = 100


def image_source(url: str, width: int, height: int) -> str:
    """Return the ``image://nanoka`` URL QML should use for *url*.

    ``QML`` builds the same string with ``encodeURIComponent``; this helper
    exists so Python tests can request exactly what the delegates request.
    """
    if not url:
        return ""
    encoded = QUrl.toPercentEncoding(url).data().decode("ascii")
    return f"image://{PROVIDER_ID}/?url={encoded}&w={int(width)}&h={int(height)}"


def parse_image_id(image_id: str) -> tuple[str, QSize]:
    """Split an image provider id into ``(url, requested size)``."""
    query = image_id[1:] if image_id.startswith("?") else image_id
    values: dict[str, str] = {}
    for pair in query.split("&"):
        if not pair:
            continue
        key, _, value = pair.partition("=")
        values[key] = QUrl.fromPercentEncoding(value.encode("utf-8"))

    try:
        width = int(values.get("w", ""))
        height = int(values.get("h", ""))
    except ValueError:
        width = height = DEFAULT_SIZE
    if width <= 0 or height <= 0:
        width = height = DEFAULT_SIZE

    return values.get("url", ""), QSize(width, height)


class NanokaImageProvider(QQuickImageProvider):
    """Asynchronous, cached ``image://nanoka`` provider."""

    def __init__(self):
        super().__init__(
            QQuickImageProvider.ImageType.Image,
            QQmlImageProviderBase.Flag.ForceAsynchronousImageLoading,
        )

    def requestImage(self, image_id, size, requested_size):  # noqa: N802
        url, requested = parse_image_id(image_id)
        if not url:
            return QImage()

        try:
            image = load_qt_image_sync(url, (requested.width(), requested.height()))
        except Exception:  # defensive: a loader bug must not kill the image thread
            logger.exception("Unexpected error loading %s", url)
            return QImage()

        if image is None or image.isNull():
            logger.debug("Image unavailable: %s", url)
            return QImage()

        # ``size`` is the out-parameter telling the engine the real image size.
        if size is not None:
            size.setWidth(image.width())
            size.setHeight(image.height())
        return image


class NanokaArtProvider(QQuickImageProvider):
    """Serve already-decoded artwork to QML under short-lived tokens.

    The details popup loads artwork through its own cache/download path, which
    yields raw bytes rather than a URL the QML image loader could fetch.  The
    controller decodes each image once and registers it here; QML asks for
    ``image://nanokaart/<token>``.  A fresh token per character busts QML's
    per-URL image cache without evicting anything globally, and :meth:`clear`
    releases the decoded image when the popup moves on.

    ``requestImage`` can be called from the QML image thread, hence the lock.
    """

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._images: dict[str, QImage] = {}
        self._lock = threading.Lock()

    def add(self, token: str, image: QImage) -> str:
        """Register *image* under *token* and return its ``image://`` URL."""
        with self._lock:
            self._images[str(token)] = image
        return f"image://{ART_PROVIDER_ID}/{token}"

    def clear(self) -> None:
        """Forget every registered image."""
        with self._lock:
            self._images.clear()

    def requestImage(self, image_id, size, requested_size):  # noqa: N802
        with self._lock:
            image = self._images.get(image_id)
        if image is None or image.isNull():
            return QImage()

        if size is not None:
            size.setWidth(image.width())
            size.setHeight(image.height())
        return image
