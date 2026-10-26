"""Regression tests for the Wayland maximize rendering bug, on the REAL app.

Root cause: a hidden native anchor (added so QtWebEngine would not recreate the
window) promoted ``centralWidget`` and every card ``QScrollArea`` into separate
Wayland subsurfaces. On maximize KWin failed to composite those sibling
surfaces, leaving black bars and shoving section headers to the window edge.
The overlay then had to fight sibling subsurfaces for z-order, which QWidget
raise could not reliably win.

The in-app browser (and thus QtWebEngine) has been removed, so the anchor is
gone and nothing is native except the top-level window. Every widget now paints
into the single main-window backing store, so a QWidget-level raise keeps the
overlay on top and there are no subsurfaces to mis-composite.

These tests boot the real ``NanokaViewer`` window and pin down:
  * the absence of native child subsurfaces (the black-bar regression guard),
  * the real ``view_btn`` -> ``open_details`` path opening the overlay,
  * overlay geometry tracking the host across repeated maximize/restore.
"""

from __future__ import annotations

import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from support import QtTestCase, flush, real_viewer

from nanoka_viewer.ui.details import CharacterDetailsPopup


def native_children(window) -> list[QWidget]:
    """Descendant widgets promoted to native Wayland subsurfaces."""
    return [
        w
        for w in window.findChildren(QWidget)
        if w.testAttribute(Qt.WidgetAttribute.WA_NativeWindow)
    ]


class NativeSubsurfaceRegressionTests(QtTestCase):
    def test_real_window_has_no_native_child_subsurfaces(self):
        """The black-bar cause: no child widget may be a native subsurface."""
        with real_viewer() as (window, card):
            offenders = native_children(window)
            self.assertEqual(
                offenders,
                [],
                "child widgets must not be native subsurfaces; they "
                "mis-composite as black bars on maximize: "
                f"{[w.objectName() or type(w).__name__ for w in offenders]}",
            )
            self.assertIsNotNone(card, "the real card should be populated")

    def test_overlay_is_a_plain_child_widget_not_a_subsurface(self):
        """The overlay must paint in the single backing store, not a surface."""
        with real_viewer() as (window, card):
            card.view_btn.click()
            flush()
            popup = self.get_popup()
            self.assertIsInstance(popup, CharacterDetailsPopup)
            self.assertFalse(
                popup.testAttribute(Qt.WidgetAttribute.WA_NativeWindow),
                "the overlay must not be a native subsurface",
            )
            self.assertIs(popup.parentWidget(), window.centralWidget())

    def test_real_view_button_opens_the_overlay(self):
        """Clicking the production View button must open the details popup."""
        with real_viewer() as (window, card):
            self.assertIsNone(self.get_popup())
            card.view_btn.click()
            flush()
            popup = self.get_popup()
            self.assertIsNotNone(popup)
            self.assertTrue(popup.isVisible())
            self.assertEqual(popup._game, "hsr")
            self.assertEqual(popup._char_id, card.char_id)

    def test_maximize_restore_relaunch_stress_on_real_window(self):
        """50x maximize -> restore -> maximize -> relaunch on the real app.

        Each cycle drives the production lifecycle: open the overlay via the
        real View button, maximize, restore, maximize again, then close and
        relaunch it. This catches both the maximize black-bar regression (no
        native subsurfaces may appear) and stale-overlay bugs on relaunch.
        """
        with real_viewer() as (window, card):
            central = window.centralWidget()

            for cycle in range(50):
                # Relaunch through the real View button.
                card.view_btn.click()
                flush()
                popup = self.get_popup()
                self.assertIsNotNone(popup, f"popup missing on cycle {cycle}")
                self.assertTrue(popup.isVisible(), f"popup hidden on open {cycle}")
                self.assertEqual(
                    native_children(window),
                    [],
                    f"native subsurface appeared on open in {cycle}",
                )

                window.showMaximized()
                flush(4)
                self._assert_overlay_ok(popup, central, card, f"max#{cycle}")

                window.showNormal()
                flush(4)
                self._assert_overlay_ok(popup, central, card, f"norm#{cycle}")

                window.showMaximized()
                flush(4)
                self._assert_overlay_ok(popup, central, card, f"max2#{cycle}")
                self.assertEqual(
                    native_children(window),
                    [],
                    f"native subsurface appeared after re-maximize in {cycle}",
                )

                # Close before the next relaunch. The popup is a shared
                # singleton: close hides it, the next View click reuses it.
                popup.close_popup()
                flush()
                self.assertFalse(
                    self.get_popup().isVisible(),
                    f"popup still visible after close in {cycle}",
                )

    def _assert_overlay_ok(self, popup, central, card, tag):
        self.assertTrue(popup.isVisible(), f"popup hidden after {tag}")
        self.assertEqual(
            popup.geometry(),
            central.rect(),
            f"popup geometry wrong after {tag}",
        )
        self.assertFalse(
            card.view_btn.underMouse(),
            f"View button stuck hovered after {tag}",
        )
        self.assertFalse(
            card.view_btn.isDown(),
            f"View button stuck pressed after {tag}",
        )


if __name__ == "__main__":
    unittest.main()
