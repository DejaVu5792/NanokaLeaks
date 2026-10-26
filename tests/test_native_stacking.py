"""Regression tests for the Wayland native-subsurface stacking bug.

Root cause (fixed earlier): a native anchor is realized inside ``centralWidget``
so QtWebEngine does not recreate the main window. On QtWayland this promotes
``centralWidget`` and its direct children - including the cards' ``QScrollArea``
- to native ``QWindow`` subsurfaces. Raising the overlay only at the QWidget
level does not reorder those subsurfaces, so the scroll area (and its bright
View buttons) could stay above the details overlay after a resize/maximize.

These tests pin down the structure that makes the bug possible and the
re-raise contract that keeps the overlay on top.
"""

from __future__ import annotations

import unittest

from PySide6.QtCore import Qt
from PySide6.QtGui import QWindow

from support import QtTestCase, flush, make_details_host, open_details_for

from nanoka_viewer.ui.details import CharacterDetailsPopup


class NativeSubsurfaceTests(QtTestCase):
    def test_native_anchor_promotes_host_and_scroll_area_to_qwindows(self):
        """Documents why plain QWidget.raise_() is not enough on Wayland."""
        window, central, scroll, _button, anchor = make_details_host(
            with_native_anchor=True
        )
        self.track_window(window)
        self.assertIsNotNone(anchor)

        self.assertTrue(
            central.testAttribute(Qt.WidgetAttribute.WA_NativeWindow),
            "the native anchor must promote centralWidget to a native surface",
        )
        self.assertTrue(
            scroll.testAttribute(Qt.WidgetAttribute.WA_NativeWindow),
            "the cards' scroll area is promoted to a native surface too",
        )

        central_window = central.windowHandle()
        scroll_window = scroll.windowHandle()
        self.assertIsInstance(central_window, QWindow)
        self.assertIsInstance(scroll_window, QWindow)
        self.assertIs(scroll_window.parent(), central_window)
        self.assertIsNot(scroll_window, central_window)

    def test_overlay_gets_its_own_native_surface_above_the_scroll_area(self):
        window, central, scroll, button, _anchor = make_details_host(
            with_native_anchor=True
        )
        self.track_window(window)

        popup = open_details_for(window, button)
        overlay_window = popup.windowHandle()
        scroll_window = scroll.windowHandle()

        self.assertIsInstance(overlay_window, QWindow)
        self.assertIsNot(overlay_window, scroll_window)
        self.assertIs(
            overlay_window.parent(),
            central.windowHandle(),
            "the overlay must live in the same native surface hierarchy",
        )
        self.assertTrue(overlay_window.isVisible())
        self.assertEqual(
            overlay_window.geometry(),
            central.rect(),
            "the native overlay surface must cover the whole host",
        )

    def test_overlay_is_re_raised_when_mapped_and_on_resize(self):
        window, central, _scroll, _button, _anchor = make_details_host(
            with_native_anchor=True
        )
        self.track_window(window)

        popup = CharacterDetailsPopup(central)
        calls = []
        original = popup.bring_to_front

        def spy():
            calls.append(1)
            original()

        popup.bring_to_front = spy
        popup.open_character("hsr", "1")
        flush()

        self.assertGreaterEqual(
            len(calls),
            2,
            "overlay must re-raise on show and again once the surface is mapped",
        )

        calls.clear()
        window.resize(window.width() - 40, window.height() - 30)
        flush()
        self.assertGreaterEqual(
            len(calls),
            1,
            "resizing the host must re-raise the overlay above native siblings",
        )

    def test_bring_to_front_raises_the_native_qwindow(self):
        window, central, _scroll, _button, _anchor = make_details_host(
            with_native_anchor=True
        )
        self.track_window(window)

        popup = open_details_for(window, _button)
        handle = popup.windowHandle()
        raised = []
        original = handle.raise_
        handle.raise_ = lambda: (raised.append(1), original())[1]

        popup.bring_to_front()
        self.assertEqual(raised, [1])

    def test_maximize_unmaximize_stress(self):
        """Maximize/unmaximize repeatedly should keep the overlay usable."""
        window, central, _scroll, button, _anchor = make_details_host(
            with_native_anchor=True
        )
        self.track_window(window)

        popup = open_details_for(window, button)

        for cycle in range(50):
            window.showMaximized()
            flush(4)

            self.assertTrue(
                popup.isVisible(),
                f"popup hidden after maximize in cycle {cycle}",
            )
            self.assertEqual(
                popup.geometry(),
                central.rect(),
                f"popup geometry wrong after maximize in cycle {cycle}",
            )
            handle = popup.windowHandle()
            self.assertIsNotNone(handle)
            self.assertTrue(
                handle.isVisible(),
                f"native handle hidden after maximize in cycle {cycle}",
            )
            self.assertFalse(
                button.underMouse(),
                f"View button stuck hovered after maximize in cycle {cycle}",
            )
            self.assertFalse(
                button.isDown(),
                f"View button stuck pressed after maximize in cycle {cycle}",
            )

            window.showNormal()
            flush(4)

            self.assertTrue(
                popup.isVisible(),
                f"popup hidden after restore in cycle {cycle}",
            )
            self.assertEqual(
                popup.geometry(),
                central.rect(),
                f"popup geometry wrong after restore in cycle {cycle}",
            )
            handle = popup.windowHandle()
            self.assertIsNotNone(handle)
            self.assertTrue(
                handle.isVisible(),
                f"native handle hidden after restore in cycle {cycle}",
            )


if __name__ == "__main__":
    unittest.main()
