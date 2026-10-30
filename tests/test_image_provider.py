"""Tests for the ``image://nanoka`` provider used by the QML cards.

The provider is the only place the QML tree touches the image cache, so its
URL grammar and its failure behaviour (null image => QML ``Image.Error``) are
worth pinning down without a QML engine.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from support import QtTestCase

from nanoka_viewer.ui import image_provider
from nanoka_viewer.ui.image_provider import (
    DEFAULT_SIZE,
    NanokaImageProvider,
    image_source,
    parse_image_id,
)

_URL = "https://static.nanoka.cc/assets/hsr/element/physical.webp"


class ImageSourceTests(unittest.TestCase):
    def test_image_source_builds_the_provider_url(self):
        source = image_source(_URL, 80, 60)

        self.assertTrue(source.startswith("image://nanoka/?"))
        self.assertIn("w=80", source)
        self.assertIn("h=60", source)

    def test_image_source_and_parse_round_trip(self):
        source = image_source(_URL, 80, 60)
        image_id = source[len("image://nanoka/") :]

        url, size = parse_image_id(image_id)

        self.assertEqual(url, _URL)
        self.assertEqual(size, QSize(80, 60))

    def test_image_source_is_empty_without_a_url(self):
        self.assertEqual(image_source("", 80, 80), "")

    def test_parse_accepts_an_id_without_the_leading_question_mark(self):
        url, size = parse_image_id("url=https%3A%2F%2Fexample.test%2Fa.png&w=8&h=9")

        self.assertEqual(url, "https://example.test/a.png")
        self.assertEqual(size, QSize(8, 9))

    def test_parse_falls_back_to_the_default_size(self):
        for image_id in ("?url=x", "?url=x&w=abc&h=def", "?url=x&w=0&h=10"):
            with self.subTest(image_id=image_id):
                self.assertEqual(
                    parse_image_id(image_id),
                    ("x", QSize(DEFAULT_SIZE, DEFAULT_SIZE)),
                )


class ImageProviderTests(QtTestCase):
    def _image(self) -> QImage:
        image = QImage(4, 3, QImage.Format.Format_ARGB32)
        image.fill(0xFF336699)
        return image

    def test_request_returns_the_loaded_image_and_size(self):
        image = self._image()
        provider = NanokaImageProvider()

        with patch.object(
            image_provider, "load_qt_image_sync", return_value=image
        ) as loader:
            size = QSize()
            result = provider.requestImage(
                "?url=https%3A%2F%2Fexample.test%2Fa.png&w=32&h=24",
                size,
                QSize(32, 24),
            )

        loader.assert_called_once_with("https://example.test/a.png", (32, 24))
        self.assertFalse(result.isNull())
        self.assertEqual(result.size(), QSize(4, 3))

    def test_request_returns_a_null_image_when_the_load_fails(self):
        provider = NanokaImageProvider()

        with patch.object(image_provider, "load_qt_image_sync", return_value=None):
            result = provider.requestImage(
                "?url=https%3A%2F%2Fexample.test%2Fa.png&w=80&h=80",
                QSize(),
                QSize(80, 80),
            )

        self.assertTrue(
            result.isNull(),
            "a failed load must yield a null image (QML turns that into "
            "Image.Error, which drives the card's placeholder)",
        )

    def test_request_without_a_url_does_not_touch_the_loader(self):
        provider = NanokaImageProvider()

        with patch.object(image_provider, "load_qt_image_sync") as loader:
            result = provider.requestImage("?w=80&h=80", QSize(), QSize(80, 80))

        self.assertTrue(result.isNull())
        loader.assert_not_called()

    def test_request_survives_an_unexpected_loader_error(self):
        provider = NanokaImageProvider()

        with patch.object(
            image_provider,
            "load_qt_image_sync",
            side_effect=RuntimeError("boom"),
        ), self.assertLogs("nanoka_viewer.ui.image_provider", level="ERROR"):
            result = provider.requestImage(
                "?url=https%3A%2F%2Fexample.test%2Fa.png&w=80&h=80",
                QSize(),
                QSize(80, 80),
            )

        self.assertTrue(result.isNull())


if __name__ == "__main__":
    unittest.main()
