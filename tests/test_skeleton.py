"""Regression tests for the shared loading placeholders."""

from __future__ import annotations

import unittest

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QWidget, QVBoxLayout

from support import QtTestCase, flush, wait

from nanoka_viewer.ui.skeleton import SkeletonBlock, start_pulse, stop_pulse


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


if __name__ == "__main__":
    unittest.main()
