"""Rule-term hover card sizing and anchoring.

The tooltip used to size itself from a window-width approximation and anchor
to the whole ``TextEdit``, so the same term could be a different width on every
card and the card sat far above the pointer.  It now takes exactly 60 % of the
real details pane width and grows upward from the hovered cursor.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from PySide6.QtCore import QObject

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
from nanoka_viewer.api.detail_models import ContentEntry

TIMEOUT = 4000
TERM_ID = "term-1"
TERM_NAME = "Gradient Beacon"
TERM_BODY = "A beacon that keeps the area lit for a short while."


class RuleTermTooltipTests(QtTestCase):
    def _open(self):
        overview = f'<a href="term:{TERM_ID}">{TERM_NAME}</a> is a rule term.'
        detail = replace(
            SAMPLE_DETAIL,
            overview=overview,
            terms=[
                ContentEntry(
                    name=TERM_NAME,
                    text=TERM_BODY,
                    term_id=TERM_ID,
                )
            ],
        )
        details_ui.load_character_detail = lambda game, char_id: detail
        window, _central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)
        wait_for(
            lambda: popup._model.state == "ready",
            timeout=TIMEOUT,
            message="the details never became ready",
        )
        wait(80)
        return popup

    def _find(self, popup, object_name):
        item = find_qml_item(popup._qml.rootObject(), object_name)
        self.assertIsNotNone(item, f"QML item {object_name!r} was not created")
        return item

    def _show_at(self, popup, overview, x, y):
        """Open the tooltip as if the pointer had entered a term at ``x``/``y``.

        Driving the hover state through real mouse events is not reliable on
        the offscreen platform: the synthetic pointer leaves the item while the
        popup's delay timer runs.  The position snapshot is a plain property, so
        set that and open the popup directly instead.
        """
        overview.setProperty("_hoverX", x)
        overview.setProperty("_hoverY", y)
        tip = overview.findChild(QObject, "termTooltip")
        self.assertIsNotNone(tip, "the term tooltip popup was not created")
        tip.setProperty("visible", True)
        wait(400)
        self.assertTrue(tip.property("visible"))
        return tip

    def test_tooltip_is_sixty_percent_of_the_details_pane(self):
        popup = self._open()
        overview = self._find(popup, "detailsOverview")
        pane = self._find(popup, "detailsScroll")

        tip = self._show_at(popup, overview, 40, 12)

        expected = round(pane.width() * 0.60)
        self.assertEqual(
            tip.property("width"),
            expected,
            "the card width must track the actual details pane, not the window",
        )

    def test_tooltip_sits_just_above_the_hovered_cursor(self):
        popup = self._open()
        overview = self._find(popup, "detailsOverview")

        hover_x = 40
        hover_y = 12
        tip = self._show_at(popup, overview, hover_x, hover_y)

        card_bottom = tip.property("y") + tip.property("height")
        self.assertAlmostEqual(
            card_bottom,
            hover_y - 12,
            delta=1,
            msg="the card must keep a short gap above the pointer",
        )
        # The pointer is on the first line, so the card necessarily extends
        # above the text item instead of being clamped to its top edge.
        self.assertLess(
            tip.property("y"),
            0,
            "the card must be allowed to render above the text item",
        )

    def test_tooltip_is_horizontally_centred_on_the_cursor(self):
        popup = self._open()
        overview = self._find(popup, "detailsOverview")
        pane = self._find(popup, "detailsScroll")

        hover_x = 40
        tip = self._show_at(popup, overview, hover_x, 12)

        pane_x = tip.property("x") + overview.mapToItem(pane, 0, 0).x()
        expected = max(
            8,
            min(
                pane.width() - tip.property("width") - 8,
                overview.mapToItem(pane, hover_x, 0).x()
                - tip.property("width") / 2,
            ),
        )
        self.assertAlmostEqual(pane_x, expected, delta=1)


if __name__ == "__main__":
    unittest.main()
