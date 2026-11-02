"""Regression tests for the image pipeline.

These cover the failure modes that made the card grid feel broken:

* the same URL at two sizes must not return one size's image,
* a warm memory hit must not read or decode the payload again,
* a corrupt disk entry must be repaired/removed instead of poisoning the cache,
* the memory cache must stay bounded,
* the disk cache must follow ``XDG_CACHE_HOME`` like the rest of the app.
"""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage, QPainter

import support

from nanoka_viewer.ui import image_loader as il


def png_bytes(width=20, height=10, color="#ff0000") -> bytes:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    return bytes(buffer.data())


def banded_png(width=100, height=200) -> bytes:
    """Red top quarter, green middle half, blue bottom quarter."""
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#ff0000"))
    painter = QPainter(image)
    try:
        painter.fillRect(0, height // 4, width, height // 2, QColor("#00ff00"))
        painter.fillRect(0, height * 3 // 4, width, height // 4, QColor("#0000ff"))
    finally:
        painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    return bytes(buffer.data())


class FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code


class FakeSession:
    def __init__(self, content: bytes | None = None, status_code: int = 200):
        self.content = content
        self.status_code = status_code
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        if self.content is None:
            raise RuntimeError("network unavailable")
        return FakeResponse(self.content, self.status_code)


class ImageLoaderTests(unittest.TestCase):
    def setUp(self):
        self.application = support.app()
        self._temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self._temp_dir.name)
        self._original_cache_dir = il.IMAGE_CACHE_DIR
        self._original_max_bytes = il.IMAGE_CACHE_MAX_BYTES
        self._original_get_session = il._get_session
        il.IMAGE_CACHE_DIR = self.cache_dir
        il._cache_clear()

    def tearDown(self):
        il.IMAGE_CACHE_DIR = self._original_cache_dir
        il.IMAGE_CACHE_MAX_BYTES = self._original_max_bytes
        il._get_session = self._original_get_session
        il._cache_clear()
        self._temp_dir.cleanup()

    def test_cache_key_includes_size(self):
        session = FakeSession(png_bytes(40, 40))
        il._get_session = lambda: session
        url = "https://example.invalid/portrait.png"

        small = il.load_qt_image_sync(url, (18, 18))
        large = il.load_qt_image_sync(url, (80, 80))

        self.assertIsNotNone(small)
        self.assertIsNotNone(large)
        self.assertEqual((small.width(), small.height()), (18, 18))
        self.assertEqual((large.width(), large.height()), (80, 80))
        self.assertEqual(
            set(il.IMAGE_CACHE),
            {(url, (18, 18)), (url, (80, 80))},
        )
        # The encoded payload is shared on disk: only one download.
        self.assertEqual(session.calls, 1)

    def test_memory_hit_does_not_touch_the_disk(self):
        url = "https://example.invalid/portrait.png"
        il._get_session = lambda: FakeSession(png_bytes())

        first = il.load_qt_image_sync(url, (18, 18))
        self.assertIsNotNone(first)

        with mock.patch.object(
            il, "_read_cache_file", side_effect=AssertionError("disk read")
        ):
            second = il.load_qt_image_sync(url, (18, 18))

        self.assertIs(second, first)
        self.assertEqual(len(il.IMAGE_CACHE), 1)

    def test_image_is_cover_cropped_not_stretched(self):
        session = FakeSession(banded_png(100, 200))
        il._get_session = lambda: session
        url = "https://example.invalid/tall.png"

        image = il.load_qt_image_sync(url, (100, 100))

        self.assertIsNotNone(image)
        self.assertEqual((image.width(), image.height()), (100, 100))
        # A stretched 100x200 source would put the blue bottom band in the
        # lower half. Cover-cropping keeps the top, so only red/green remain.
        self.assertEqual(image.pixelColor(50, 10).name(), "#ff0000")
        self.assertEqual(image.pixelColor(50, 90).name(), "#00ff00")

    def test_corrupt_disk_entry_is_replaced(self):
        url = "https://example.invalid/portrait.png"
        cache_file = self.cache_dir / f"{hashlib.md5(url.encode()).hexdigest()}.png"
        cache_file.write_bytes(b"definitely not an image")

        session = FakeSession(png_bytes())
        il._get_session = lambda: session

        image = il.load_qt_image_sync(url, (18, 18))

        self.assertIsNotNone(image)
        self.assertEqual(session.calls, 1)
        self.assertTrue(cache_file.exists())
        self.assertNotEqual(cache_file.read_bytes(), b"definitely not an image")

    def test_corrupt_disk_entry_is_removed_when_offline(self):
        url = "https://example.invalid/portrait.png"
        cache_file = self.cache_dir / f"{hashlib.md5(url.encode()).hexdigest()}.png"
        cache_file.write_bytes(b"still not an image")

        il._get_session = lambda: FakeSession(None)

        self.assertIsNone(il.load_qt_image_sync(url, (18, 18)))
        self.assertFalse(cache_file.exists())

    def test_memory_cache_is_bounded(self):
        il.IMAGE_CACHE_MAX_BYTES = 1000
        image = QImage(20, 10, QImage.Format.Format_ARGB32)  # 20*10*4 = 800 bytes

        for index in range(5):
            il._cache_put((f"url-{index}", (20, 10)), image)

        self.assertLessEqual(len(il.IMAGE_CACHE), 2)
        self.assertLessEqual(il._CACHE_BYTES, 1000)

    def test_clear_image_cache_drops_memory_and_disk(self):
        url = "https://example.invalid/portrait.png"
        il._get_session = lambda: FakeSession(png_bytes())
        il.load_qt_image_sync(url, (18, 18))
        self.assertTrue(il.IMAGE_CACHE)

        il.clear_image_cache()

        self.assertFalse(il.IMAGE_CACHE)
        self.assertEqual(il._CACHE_BYTES, 0)
        self.assertEqual(list(self.cache_dir.iterdir()), [])


class ImageCacheLocationTests(unittest.TestCase):
    def test_disk_cache_lives_under_the_shared_cache_dir(self):
        self.assertEqual(il.IMAGE_CACHE_DIR, il.CACHE_DIR / "images")


if __name__ == "__main__":
    unittest.main()
