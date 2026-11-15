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
from unittest.mock import patch

from PySide6.QtCore import (
    QBuffer,
    QEvent,
    QIODevice,
    QPoint,
    QPointF,
    QSize,
    Qt,
)
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QWheelEvent
from PySide6.QtWidgets import QApplication

from support import (
    SAMPLE_DETAIL,
    QtTestCase,
    click_qml,
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
    def _open_with_art(self, art_bytes=None):
        details_ui.load_character_art = lambda url: (
            art_bytes if art_bytes is not None else make_banded_png()
        )
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

    def _point_in(self, popup, item, x, y):
        point = item.mapToItem(popup._qml.rootObject(), x, y)
        return QPoint(round(point.x()), round(point.y()))

    def _send_mouse(self, popup, kind, point, buttons, button):
        event = QMouseEvent(
            kind,
            QPointF(point),
            QPointF(popup._qml.mapToGlobal(point)),
            button,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(popup._qml, event)
        flush(2)

    def _drag(self, popup, item, start, dx, dy, steps=6):
        left = Qt.MouseButton.LeftButton
        none = Qt.MouseButton.NoButton
        end = QPoint(start.x() + dx, start.y() + dy)
        self._send_mouse(popup, QEvent.Type.MouseButtonPress, start, left, left)
        for step in range(1, steps + 1):
            point = QPoint(
                round(start.x() + dx * step / steps),
                round(start.y() + dy * step / steps),
            )
            self._send_mouse(popup, QEvent.Type.MouseMove, point, left, none)
        self._send_mouse(popup, QEvent.Type.MouseButtonRelease, end, none, left)
        wait(40)

    def _wheel(self, popup, item, delta=120):
        point = self._point_in(popup, item, item.width() / 2, item.height() / 2)
        event = QWheelEvent(
            QPointF(point),
            QPointF(popup._qml.mapToGlobal(point)),
            QPoint(0, 0),
            QPoint(0, delta),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(popup._qml, event)
        flush()

    def _cursor_after(self, popup, kind, point, buttons, button):
        """Send one mouse event and return the widget cursor it produced."""
        self._send_mouse(popup, kind, point, buttons, button)
        return popup._qml.cursor().shape()

    def test_artwork_shows_drag_cursors(self):
        popup = self._open_with_art()
        drag = self._find(popup, "detailArtDrag")

        # Stay clear of the selectable name/meta overlay at the bottom.
        point = self._point_in(
            popup, drag, drag.width() / 2, drag.height() * 0.2
        )
        left = Qt.MouseButton.LeftButton
        none = Qt.MouseButton.NoButton

        self.assertEqual(
            self._cursor_after(
                popup, QEvent.Type.MouseMove, point, none, none
            ),
            Qt.CursorShape.OpenHandCursor,
            "draggable artwork must advertise itself with the open hand",
        )
        self.assertEqual(
            self._cursor_after(
                popup, QEvent.Type.MouseButtonPress, point, left, left
            ),
            Qt.CursorShape.ClosedHandCursor,
            "dragging the artwork must show the closed hand",
        )
        self.assertEqual(
            self._cursor_after(
                popup, QEvent.Type.MouseButtonRelease, point, none, left
            ),
            Qt.CursorShape.OpenHandCursor,
            "releasing must restore the open hand",
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

    def test_drag_pans_artwork_and_reset_restores_the_crop(self):
        popup = self._open_with_art()
        art = self._find(popup, "detailArt")
        drag = self._find(popup, "detailArtDrag")
        reset = self._find(popup, "detailArtReset")

        original = (art.x(), art.y())
        self.assertFalse(
            reset.isVisible(),
            "the reset button must stay hidden until the artwork moves",
        )

        # Start in the upper part of the column: the bottom is the selectable
        # name/meta overlay, which owns drags there.
        start = self._point_in(popup, drag, drag.width() / 2, drag.height() * 0.2)
        self._drag(popup, drag, start, 0, -120)

        self.assertLess(
            art.y(), original[1], "dragging up must move the artwork up"
        )
        self.assertTrue(
            reset.isVisible(),
            "a moved artwork must expose the reset button",
        )

        click_qml(popup._qml, reset)
        flush()
        self.assertEqual((art.x(), art.y()), original)
        self.assertFalse(
            reset.isVisible(),
            "the reset button must disappear again after resetting",
        )

    def test_wheel_zooms_artwork_and_reset_restores_the_crop(self):
        popup = self._open_with_art()
        art = self._find(popup, "detailArt")
        drag = self._find(popup, "detailArtDrag")
        reset = self._find(popup, "detailArtReset")

        original = (art.x(), art.y(), art.width(), art.height())

        # Wheel down at the minimum zoom is a no-op, so nothing to reset.
        self._wheel(popup, drag, -120)
        self.assertEqual(
            (art.x(), art.y(), art.width(), art.height()), original
        )
        self.assertFalse(reset.isVisible())

        self._wheel(popup, drag, 240)
        self.assertGreater(art.width(), original[2], "the artwork must grow")
        self.assertGreater(art.height(), original[3], "the artwork must grow")
        self.assertTrue(
            reset.isVisible(),
            "a zoomed artwork must expose the reset button",
        )

        click_qml(popup._qml, reset)
        flush()
        self.assertEqual((art.x(), art.y(), art.width(), art.height()), original)
        self.assertFalse(reset.isVisible())

    def test_new_artwork_starts_from_its_default_crop(self):
        popup = self._open_with_art()
        drag = self._find(popup, "detailArtDrag")
        reset = self._find(popup, "detailArtReset")

        self._wheel(popup, drag, 240)
        self.assertTrue(reset.isVisible())
        old_source = popup._model.artSource

        popup.open_character("hsr", "2")
        wait_for(
            lambda: popup._art_thread is None
            and popup._model.artState == "ready"
            and popup._model.artSource != old_source,
            timeout=4000,
            message="the second character's artwork never loaded",
        )
        wait(80)

        frame = self._find(popup, "detailArtFrame")
        self.assertEqual(frame.property("zoom"), 1.0)
        self.assertFalse(
            reset.isVisible(),
            "a new character must not inherit the previous zoom/pan",
        )

    def test_reset_returns_to_the_smart_centered_crop(self):
        # A square artwork is wider than the column once it covers it, so the
        # centroid can actually shift the crop.
        with (
            patch.object(details_ui, "get_setting", return_value=True),
            patch.object(details_ui, "detail_centroid_x", return_value=0.2),
        ):
            popup = self._open_with_art(make_banded_png(400, 400))

        art = self._find(popup, "detailArt")
        drag = self._find(popup, "detailArtDrag")
        reset = self._find(popup, "detailArtReset")
        frame_width = round(popup.panel_rect().width() * 0.25)
        centred_x = round(frame_width / 2 - 0.5 * art.width())
        smart_x = round(frame_width / 2 - 0.2 * art.width())

        self.assertAlmostEqual(popup._model.artFocusX, 0.2)
        self.assertAlmostEqual(
            art.x(),
            smart_x,
            delta=1,
            msg="the default crop must follow the detail centroid",
        )
        self.assertGreater(
            abs(art.x() - centred_x),
            5,
            "the fixture must make the smart crop differ from the centre",
        )

        start = self._point_in(popup, drag, drag.width() / 2, drag.height() * 0.2)
        self._drag(popup, drag, start, 100, 0)
        self.assertNotEqual(art.x(), smart_x)

        click_qml(popup._qml, reset)
        flush()
        self.assertAlmostEqual(
            art.x(),
            smart_x,
            delta=1,
            msg="reset must return to the smart-centred crop, not the centre",
        )
        self.assertFalse(reset.isVisible())

    def test_geometric_crop_when_smart_centering_is_off(self):
        with (
            patch.object(details_ui, "get_setting", return_value=False),
            patch.object(
                details_ui,
                "detail_centroid_x",
                side_effect=AssertionError("centroid must not be computed"),
            ),
        ):
            popup = self._open_with_art(make_banded_png(400, 400))

        art = self._find(popup, "detailArt")
        frame_width = round(popup.panel_rect().width() * 0.25)
        centred_x = round(frame_width / 2 - 0.5 * art.width())

        self.assertEqual(popup._model.artFocusX, 0.5)
        self.assertAlmostEqual(
            art.x(),
            centred_x,
            delta=1,
            msg="smart centering off must restore the geometric centre crop",
        )

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
