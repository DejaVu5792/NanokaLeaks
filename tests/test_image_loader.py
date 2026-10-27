"""Regression tests for the image pipeline.

These cover the failure modes that made the card grid feel broken:

* the same URL at two sizes must not return one size's pixmap,
* a corrupt disk entry must be repaired/removed instead of poisoning the cache,
* the memory cache must stay bounded,
* cancelling a request must not fire its callback,
* requests are coalesced per (url, size), not per URL.
"""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage, QPixmap

import support

from nanoka_viewer.ui import image_loader as il


def png_bytes(width=20, height=10, color="#ff0000") -> bytes:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
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
        with il._LOCK:
            il._CALLBACKS.clear()

    def tearDown(self):
        il.IMAGE_CACHE_DIR = self._original_cache_dir
        il.IMAGE_CACHE_MAX_BYTES = self._original_max_bytes
        il._get_session = self._original_get_session
        il._cache_clear()
        with il._LOCK:
            il._CALLBACKS.clear()
        self._temp_dir.cleanup()

    def test_cache_key_includes_size(self):
        session = FakeSession(png_bytes(40, 40))
        il._get_session = lambda: session
        url = "https://example.invalid/portrait.png"

        small = il.load_qt_image(url, (18, 18))
        large = il.load_qt_image(url, (80, 80))

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
        pixmap = QPixmap(20, 10)  # 20*10*4 = 800 bytes

        for index in range(5):
            il._cache_put((f"url-{index}", (20, 10)), pixmap)

        self.assertLessEqual(len(il.IMAGE_CACHE), 2)
        self.assertLessEqual(il._CACHE_BYTES, 1000)

    def test_cancelled_request_is_not_invoked(self):
        key = ("https://example.invalid/x.png", (18, 18))
        calls = []
        request = il.ImageRequest(key, calls.append)
        with il._LOCK:
            il._CALLBACKS[key] = [request]

        request.cancel()
        il._handle_image_loaded(key, QImage(10, 10, QImage.Format.Format_ARGB32))

        self.assertEqual(calls, [])
        self.assertNotIn(key, il._CALLBACKS)

    def test_requests_are_coalesced_per_size(self):
        url = "https://example.invalid/x.png"
        submitted = []

        def fake_submit(fn, *args, **kwargs):
            submitted.append((fn, args, kwargs))

        with mock.patch.object(il.image_executor, "submit", side_effect=fake_submit):
            first = il.request_image(url, lambda pm: None, (18, 18))
            second = il.request_image(url, lambda pm: None, (18, 18))
            third = il.request_image(url, lambda pm: None, (80, 80))

        self.assertEqual(len(submitted), 2)
        self.assertIs(il._CALLBACKS[(url, (18, 18))][0], first)
        self.assertIs(il._CALLBACKS[(url, (18, 18))][1], second)
        self.assertIs(il._CALLBACKS[(url, (80, 80))][0], third)

        first.cancel()
        second.cancel()
        third.cancel()


if __name__ == "__main__":
    unittest.main()
