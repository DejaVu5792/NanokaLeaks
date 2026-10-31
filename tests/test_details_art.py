"""Regression tests for the artwork fixes in the details view.

* ``_ArtLabel`` focus-crops horizontally (centre by default, saliency centroid
  when available) and keeps the top of the artwork (where the character's face
  is) instead of relying on QLabel clipping.
* ``_set_art_message`` drops the cached source pixmap, otherwise the next
  resize resurrected the previous character's artwork over "Art unavailable".
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from PySide6.QtCore import QBuffer, QIODevice, QSize
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QWidget

from support import (
    SAMPLE_DETAIL,
    QtTestCase,
    flush,
    make_details_host,
    open_details_for,
    wait,
)

import nanoka_viewer.ui.details as details
from nanoka_viewer.ui.details import CharacterDetailsPopup, _ArtLabel

RED = "#ff0000"
GREEN = "#00ff00"
BLUE = "#0000ff"


def make_banded_pixmap(width: int = 100, height: int = 200) -> QPixmap:
    """Red top quarter, green middle half, blue bottom quarter."""
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(RED))
    painter = QPainter(pixmap)
    try:
        painter.fillRect(0, height // 4, width, height // 2, QColor(GREEN))
        painter.fillRect(0, height * 3 // 4, width, height // 4, QColor(BLUE))
    finally:
        painter.end()
    return pixmap


def make_horizontal_bands(width: int = 300, height: int = 100) -> QPixmap:
    """Red left third, green middle third, blue right third."""
    pixmap = QPixmap(width, height)
    third = width // 3
    painter = QPainter(pixmap)
    try:
        painter.fillRect(0, 0, third, height, QColor(RED))
        painter.fillRect(third, 0, third, height, QColor(GREEN))
        painter.fillRect(third * 2, 0, width - third * 2, height, QColor(BLUE))
    finally:
        painter.end()
    return pixmap


class ArtLabelTests(QtTestCase):
    def test_scaled_art_is_top_cropped(self):
        label = _ArtLabel()
        self.addCleanup(label.deleteLater)
        label.resize(100, 100)
        label.show()
        flush()

        label.set_source(make_banded_pixmap())
        flush()

        pixmap = label.pixmap()
        self.assertIsNotNone(pixmap)
        self.assertEqual(pixmap.size(), QSize(100, 100))
        image = pixmap.toImage()
        # A 100x200 source scaled to cover a 100x100 label keeps the top band
        # (the face) and crops the bottom, rather than centring vertically.
        self.assertEqual(image.pixelColor(50, 10).name(), RED)
        self.assertEqual(image.pixelColor(50, 90).name(), GREEN)

    def test_resize_refits_artwork(self):
        label = _ArtLabel()
        self.addCleanup(label.deleteLater)
        label.resize(100, 100)
        label.show()
        flush()
        label.set_source(make_banded_pixmap())
        flush()

        label.resize(140, 90)
        wait(80)  # the rescale is coalesced behind a short debounce

        pixmap = label.pixmap()
        self.assertIsNotNone(pixmap)
        self.assertEqual(pixmap.size(), QSize(140, 90))

    def test_focus_x_crops_to_the_requested_side(self):
        source = make_horizontal_bands()
        for focus_x, expected in ((0.0, RED), (0.5, GREEN), (1.0, BLUE)):
            with self.subTest(focus_x=focus_x):
                label = _ArtLabel()
                self.addCleanup(label.deleteLater)
                label.resize(100, 100)
                label.show()
                flush()

                label.set_source(source, focus_x)
                flush()

                image = label.pixmap().toImage()
                self.assertEqual(image.pixelColor(50, 50).name(), expected)

    def test_focus_x_survives_a_resize(self):
        label = _ArtLabel()
        self.addCleanup(label.deleteLater)
        label.resize(100, 100)
        label.show()
        flush()
        label.set_source(make_horizontal_bands(), 1.0)
        flush()

        label.resize(120, 100)
        wait(80)

        image = label.pixmap().toImage()
        self.assertEqual(image.pixelColor(60, 50).name(), BLUE)

    def test_art_text_is_anchored_to_the_bottom(self):
        host = QWidget()
        self.addCleanup(host.deleteLater)
        popup = CharacterDetailsPopup(host)
        self.addCleanup(popup.deleteLater)

        frame = popup._build_art_panel(SAMPLE_DETAIL)
        overlay = frame.findChild(QFrame, "detailArtOverlay")
        self.assertIsNotNone(overlay)
        layout = overlay.layout()
        self.assertIsNotNone(layout.itemAt(0).spacerItem())
        self.assertIsNotNone(overlay.findChild(QLabel, "detailArtName"))

    def test_art_message_drops_the_cached_source(self):
        host = QWidget()
        self.addCleanup(host.deleteLater)
        popup = CharacterDetailsPopup(host)
        self.addCleanup(popup.deleteLater)

        label = _ArtLabel()
        self.addCleanup(label.deleteLater)
        label.resize(100, 100)
        label.show()
        flush()
        label.set_source(make_banded_pixmap())
        flush()
        popup._art_label = label

        popup._set_art_message("Art unavailable")

        self.assertIsNone(label._source)
        self.assertEqual(label.text(), "Art unavailable")

        # A resize used to call _rescale() and resurrect the old artwork.
        label.resize(140, 120)
        flush()
        self.assertEqual(label.text(), "Art unavailable")
        self.assertIsNone(label._source)


class ArtSkeletonTests(QtTestCase):
    def _png_bytes(self) -> bytes:
        image = QImage(120, 200, QImage.Format.Format_ARGB32)
        image.fill(QColor("#ff0000"))
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        self.assertTrue(image.save(buffer, "PNG"))
        return bytes(buffer.data())

    def test_artwork_replaces_the_skeleton_that_reserved_its_space(self):
        details.load_character_art = lambda url: self._png_bytes()
        details.load_character_detail = lambda game, char_id: replace(
            SAMPLE_DETAIL, art_url="https://example.invalid/art.png"
        )

        window, _central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)

        for _ in range(60):
            if popup._art_label is not None and popup._art_label._source is not None:
                break
            wait(20)
        wait(300)  # the artwork cross-fades over the skeleton

        self.assertIsNotNone(popup._art_label)
        self.assertIsNotNone(popup._art_label._source)
        self.assertIsNone(
            popup._art_skeleton,
            "the art skeleton must be dropped once the artwork is visible",
        )


if __name__ == "__main__":
    unittest.main()
