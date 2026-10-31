"""Regression tests for the artwork fixes in the details view.

* The artwork is scaled to cover its column, centre-cropped horizontally and
  keeps the top of the image (where the character's face is) instead of
  centring the vertical crop.
* ``_set_art_message`` drops the decoded artwork, otherwise the next character
  would show the previous one's art over "Art unavailable".
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QSize
from PySide6.QtGui import QColor, QImage, QPainter

from support import (
    SAMPLE_DETAIL,
    QtTestCase,
    find_qml_item,
    flush,
    make_details_host,
    open_details_for,
    wait,
    wait_for,
)

import nanoka_viewer.ui.details as details_ui

RED = "#ff0000"
GREEN = "#00ff00"
BLUE = "#0000ff"

ART_URL = "https://example.invalid/art.png"
HEADER_HEIGHT = 46


def make_banded_png(width: int = 100, height: int = 400) -> bytes:
    """Red top quarter, green middle half, blue bottom quarter."""
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(RED))
    painter = QPainter(image)
    try:
        painter.fillRect(0, height // 4, width, height // 2, QColor(GREEN))
        painter.fillRect(0, height * 3 // 4, width, height // 4, QColor(BLUE))
    finally:
        painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


class ArtworkTests(QtTestCase):
    def _open_with_art(self):
        details_ui.load_character_art = lambda url: make_banded_png()
        details_ui.load_character_detail = lambda game, char_id: replace(
            SAMPLE_DETAIL, art_url=ART_URL
        )

        window, _central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)
        wait_for(
            lambda: popup._art_thread is None
            and popup._model.artState == "ready",
            timeout=4000,
            message="the artwork never became visible",
        )
        art = find_qml_item(popup._qml.rootObject(), "detailArt")
        self.assertIsNotNone(art, "the QML artwork item was not created")
        # The provider hands the bytes over asynchronously; the fade-in only
        # reaches full opacity once the texture exists.
        wait_for(
            lambda: float(art.property("opacity")) >= 0.99,
            timeout=4000,
            message="the QML image never decoded",
        )
        wait(80)
        return popup

    def _find(self, popup, object_name):
        item = find_qml_item(popup._qml.rootObject(), object_name)
        self.assertIsNotNone(item, f"QML item {object_name!r} was not created")
        return item

    def _assert_colour(self, actual, expected, message):
        """Compare colours with a tolerance for smooth-scaling artifacts."""
        self.assertLessEqual(
            max(
                abs(a - e)
                for a, e in zip(
                    actual.getRgb()[:3], QColor(expected).getRgb()[:3]
                )
            ),
            6,
            f"{message}: got {actual.name()}, expected {expected}",
        )

    def test_art_is_cover_cropped_and_keeps_the_top(self):
        popup = self._open_with_art()
        art = self._find(popup, "detailArt")
        frame_height = popup.panel_rect().height() - HEADER_HEIGHT

        self.assertEqual(art.y(), 0, "the crop must keep the top of the artwork")
        self.assertGreater(
            art.height(),
            frame_height,
            "a tall artwork must be scaled to cover the column",
        )
        self.assertAlmostEqual(
            art.x(),
            (round(popup.panel_rect().width() * 0.25) - art.width()) / 2,
            delta=1,
            msg="the horizontal crop must be centred",
        )

        image = popup.grab().toImage()
        panel = popup.panel_rect()
        x = panel.left() + round(panel.width() * 0.25) // 2
        top = panel.top() + HEADER_HEIGHT

        self._assert_colour(
            image.pixelColor(x, top + 10),
            RED,
            "the artwork's top band must stay at the top of the column",
        )
        # A vertically centred crop would already show the green band here.
        self._assert_colour(
            image.pixelColor(x, top + 150),
            RED,
            "the top band must still cover this row",
        )
        lower = image.pixelColor(x, top + 400)
        self.assertGreater(
            lower.green(),
            lower.red(),
            "the lower part of the column must show the green band",
        )

    def test_resize_refits_the_artwork(self):
        popup = self._open_with_art()
        art = self._find(popup, "detailArt")
        old_height = art.height()

        popup._host.window().resize(1200, 800)
        flush()
        wait(200)

        self.assertGreater(
            art.height(),
            old_height,
            "the artwork must cover the taller column after a resize",
        )
        self.assertGreaterEqual(
            art.width(), round(popup.panel_rect().width() * 0.25) - 1
        )

    def test_art_text_is_anchored_to_the_bottom(self):
        popup = self._open_with_art()
        column = self._find(popup, "detailsArtColumn")
        name = self._find(popup, "detailArtName")
        meta = self._find(popup, "detailArtMeta")

        self.assertEqual(name.property("text"), SAMPLE_DETAIL.name)
        self.assertEqual(meta.property("text"), " · ".join(SAMPLE_DETAIL.badges))

        name_bottom = name.mapToItem(column, QPointF(0, name.height())).y()
        meta_top = meta.mapToItem(column, QPointF(0, 0)).y()
        meta_bottom = meta.mapToItem(column, QPointF(0, meta.height())).y()

        self.assertLess(name_bottom, meta_top + 1, "name must sit above the meta")
        self.assertAlmostEqual(
            meta_bottom,
            column.height() - 14,
            delta=2,
            msg="the name/meta block must hug the bottom of the art column",
        )

    def test_art_message_drops_the_cached_image(self):
        popup = self._open_with_art()
        token = popup._model.artSource.rsplit("/", 1)[-1]

        popup._set_art_message("Art unavailable")
        flush()

        self.assertEqual(popup._model.artState, "unavailable")
        self.assertEqual(popup._model.artSource, "")
        self.assertEqual(popup._model.artMessage, "Art unavailable")

        size = QSize()
        self.assertTrue(
            popup._art_provider.requestImage(token, size, QSize()).isNull(),
            "the decoded artwork must be dropped from the provider",
        )

        # A resize used to resurrect the previous character's artwork.
        popup._host.resize(1000, 700)
        flush()
        wait(80)
        self.assertEqual(popup._model.artState, "unavailable")

    def test_artwork_replaces_the_skeleton(self):
        popup = self._open_with_art()

        self.assertEqual(popup._model.artState, "ready")
        self.assertFalse(
            self._find(popup, "detailArtSkeleton").isVisible(),
            "the art skeleton must be dropped once the artwork is visible",
        )
        self.assertTrue(self._find(popup, "detailArt").isVisible())


if __name__ == "__main__":
    unittest.main()
