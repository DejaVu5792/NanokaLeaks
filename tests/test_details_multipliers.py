"""Zebra striping for skill multiplier tables.

Multiplier rows are full-width label/value pairs.  Without a background they
read as one block, so every other row is tinted to keep wide tables scannable.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from support import (
    SAMPLE_DETAIL,
    QtTestCase,
    click_qml,
    find_qml_item,
    find_qml_items,
    flush,
    make_details_host,
    open_details_for,
    wait,
    wait_for,
)

import nanoka_viewer.ui.details as details_ui
from nanoka_viewer.api.detail_models import SkillDetail

TIMEOUT = 4000
MULTIPLIERS = [
    ("Lv 1", "50%"),
    ("Lv 2", "60%"),
    ("Lv 3", "70%"),
    ("Lv 4", "80%"),
]


class MultiplierZebraTests(QtTestCase):
    def _open(self):
        detail = replace(
            SAMPLE_DETAIL,
            skills=[SkillDetail("Skill", "Attack", "Body", MULTIPLIERS, 1)],
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

    def test_multiplier_rows_alternate_their_background(self):
        popup = self._open()
        root = popup._qml.rootObject()

        toggle = find_qml_item(root, "skillToggle")
        self.assertIsNotNone(toggle, "the skill row was not created")
        click_qml(popup._qml, toggle)
        flush()

        rows = find_qml_items(root, "skillMultiplierRow")
        self.assertEqual(len(rows), len(MULTIPLIERS))

        colors = [row.property("color") for row in rows]
        for row in rows:
            self.assertGreater(row.height(), 0, "zebra rows must have height")
            self.assertGreater(row.width(), 0, "zebra rows must span the body")
        # Even rows let the framed body show through; odd rows are tinted.
        self.assertEqual(colors[0].alpha(), 0)
        self.assertEqual(colors[2].alpha(), 0)
        self.assertEqual(colors[1].alpha(), 255)
        self.assertEqual(colors[3].alpha(), 255)
        self.assertNotEqual(colors[0], colors[1])
        self.assertEqual(colors[0], colors[2])
        self.assertEqual(colors[1], colors[3])


if __name__ == "__main__":
    unittest.main()
