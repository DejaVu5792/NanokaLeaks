"""Regression tests for the artwork fixes in the details view.

* ``_ArtLabel`` centre-crops the scaled artwork instead of relying on QLabel
  clipping (the old KeepAspectRatioByExpanding pixmap was cut at the top-left).
* ``_set_art_message`` drops the cached source pixmap, otherwise the next
  resize resurrected the previous character's artwork over "Art unavailable".
"""

from __future__ import annotations

import unittest

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from support import QtTestCase, flush

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


class ArtLabelTests(QtTestCase):
    def test_scaled_art_is_centre_cropped(self):
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
        # A 100x200 source scaled to cover a 100x100 label must be cropped to
        # its vertically centred band, not its top-left corner.
        self.assertEqual(image.pixelColor(50, 50).name(), GREEN)
        self.assertEqual(image.pixelColor(2, 2).name(), GREEN)
        self.assertEqual(image.pixelColor(97, 97).name(), GREEN)

    def test_resize_refits_artwork(self):
        label = _ArtLabel()
        self.addCleanup(label.deleteLater)
        label.resize(100, 100)
        label.show()
        flush()
        label.set_source(make_banded_pixmap())
        flush()

        label.resize(140, 90)
        flush()

        pixmap = label.pixmap()
        self.assertIsNotNone(pixmap)
        self.assertEqual(pixmap.size(), QSize(140, 90))

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


if __name__ == "__main__":
    unittest.main()
