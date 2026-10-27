"""Regression tests for the shared loading placeholders."""

from __future__ import annotations

import unittest

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QPalette, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout

from support import QtTestCase, flush, wait

from nanoka_viewer.ui.skeleton import (
    SkeletonBlock,
    SkeletonThumbnail,
    start_pulse,
    stop_pulse,
)


class SkeletonBlockTests(QtTestCase):
    def test_block_paints_with_the_skeleton_blend(self):
        block = SkeletonBlock(radius=6)
        block.setFixedSize(60, 24)
        block.show()
        self.addCleanup(block.deleteLater)
        flush()

        palette = self.application.palette()
        midlight = palette.color(QPalette.ColorRole.Midlight)
        mid = palette.color(QPalette.ColorRole.Mid)
        expected = QColor(
            (midlight.red() + mid.red()) // 2,
            (midlight.green() + mid.green()) // 2,
            (midlight.blue() + mid.blue()) // 2,
        )
        actual = block.grab().toImage().pixelColor(30, 12)
        self.assertEqual(actual.name(), expected.name())

    def test_pulse_animates_alpha_without_a_graphics_effect(self):
        block = SkeletonBlock()
        block.setFixedSize(40, 12)
        self.addCleanup(block.deleteLater)

        start_pulse(block)
        wait(120)
        self.assertIsNone(
            block.graphicsEffect(),
            "skeleton pulses must not rerender widgets through a graphics effect",
        )
        self.assertLess(block.pulseAlpha, 255)

        stop_pulse(block)
        self.assertEqual(block.pulseAlpha, 255)

    def test_container_pulses_every_skeleton_inside_it(self):
        container = QWidget()
        self.addCleanup(container.deleteLater)
        layout = QVBoxLayout(container)
        first = SkeletonBlock()
        first.setFixedHeight(10)
        second = SkeletonBlock()
        second.setFixedHeight(10)
        layout.addWidget(first)
        layout.addWidget(second)

        pulse = start_pulse(container)
        wait(120)

        self.assertIsNotNone(pulse)
        self.assertLess(first.pulseAlpha, 255)
        self.assertLess(second.pulseAlpha, 255)

        stop_pulse(container)
        self.assertEqual(first.pulseAlpha, 255)
        self.assertEqual(second.pulseAlpha, 255)


class SkeletonThumbnailTests(QtTestCase):
    def _pixmap(self, colour="#ff0000") -> QPixmap:
        pixmap = QPixmap(80, 80)
        pixmap.fill(QColor(colour))
        return pixmap

    def test_thumbnail_is_the_requested_size_in_both_states(self):
        thumbnail = SkeletonThumbnail(80, 80, radius=8)
        thumbnail.show()
        self.addCleanup(thumbnail.deleteLater)
        flush()

        self.assertEqual(thumbnail.size(), QSize(80, 80))
        self.assertFalse(thumbnail.has_image)
        self.assertIsNone(thumbnail.graphicsEffect())

        thumbnail.set_image(self._pixmap())
        wait(260)  # let the short cross-fade finish

        self.assertTrue(thumbnail.has_image)
        self.assertEqual(thumbnail.size(), QSize(80, 80))
        self.assertEqual(thumbnail.pulseAlpha, 255)
        image = thumbnail.grab().toImage()
        self.assertEqual(image.pixelColor(40, 40).name(), "#ff0000")
        # The image is clipped to the same rounded shape as the skeleton.
        self.assertNotEqual(image.pixelColor(1, 1).name(), "#ff0000")

    def test_failed_thumbnail_keeps_the_footprint_and_stops_pulsing(self):
        thumbnail = SkeletonThumbnail(80, 80)
        thumbnail.show()
        self.addCleanup(thumbnail.deleteLater)
        flush()

        thumbnail.set_failed()
        flush()

        self.assertFalse(thumbnail.has_image)
        self.assertEqual(thumbnail.size(), QSize(80, 80))
        self.assertEqual(thumbnail.pulseAlpha, 255)

    def test_hidden_thumbnail_does_not_animate_a_fade(self):
        thumbnail = SkeletonThumbnail(80, 80)
        self.addCleanup(thumbnail.deleteLater)

        thumbnail.set_image(self._pixmap())
        flush()

        self.assertTrue(thumbnail.has_image)
        image = thumbnail.grab().toImage()
        self.assertEqual(image.pixelColor(40, 40).name(), "#ff0000")


if __name__ == "__main__":
    unittest.main()
