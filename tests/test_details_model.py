"""Unit tests for the QML-facing details view model.

The popup's QML tree binds to this model, so its shapes (rows of stats and
build sections, collapsed skill titles, art states) are part of the contract.
These tests run without a QML engine on purpose: the state machine must stay
testable on its own.
"""

from __future__ import annotations

import unittest

from support import QtTestCase

from nanoka_viewer.api.details import (
    BuildSection,
    CharacterDetail,
    ContentEntry,
    ExtraSection,
    SkillDetail,
)
from nanoka_viewer.ui.details_model import DetailsViewModel


def make_detail(**overrides) -> CharacterDetail:
    values = {
        "game": "hsr",
        "char_id": "1",
        "name": "Hero",
        "subtitle": "5-star · Harmony · Path of Harmony",
        "overview": "A test character.",
        "level_label": "Lv. 80",
        "badges": ["5-star", "Harmony"],
        "stats": [("HP", "1000"), ("ATK", "500"), ("DEF", "400")],
        "build": [
            BuildSection("Relic", ["A", "B"]),
            BuildSection("Light Cone", ["C"]),
        ],
        "skills": [SkillDetail("Basic", "Attack", "Hits.", [("Lv1", "50%")], 3)],
        "extras": [ExtraSection("Passives", [ContentEntry("Trace", "Body")])],
        "art_url": "https://example.test/art.png",
    }
    values.update(overrides)
    return CharacterDetail(**values)


class DetailsViewModelTests(QtTestCase):
    def setUp(self):
        super().setUp()
        self.model = DetailsViewModel()
        self.addCleanup(self.model.deleteLater)

    def test_detail_is_shaped_for_the_qml_grids(self):
        self.model.set_detail(make_detail())

        self.assertEqual(self.model.state, "ready")
        self.assertEqual(self.model.name, "Hero")
        self.assertEqual(self.model.badgesText, "5-star · Harmony")
        self.assertEqual(self.model.levelLabel, "Lv. 80")

        # Two stats per row: a QML Repeater can only add one item per entry.
        self.assertEqual(
            self.model.statRows,
            [
                [
                    {"label": "HP", "value": "1000"},
                    {"label": "ATK", "value": "500"},
                ],
                [{"label": "DEF", "value": "400"}],
            ],
        )

        self.assertEqual(self.model.buildState, "ready")
        self.assertEqual(len(self.model.buildRows), 1)
        self.assertEqual(
            [section["title"] for section in self.model.buildRows[0]],
            ["Relic", "Light Cone"],
        )

    def test_badge_parts_are_dropped_from_the_subtitle(self):
        self.model.set_detail(make_detail())

        self.assertEqual(self.model.subtitle, "Path of Harmony")
        self.assertTrue(self.model.hasOverview)

    def test_skills_and_extras_keep_their_nested_content(self):
        self.model.set_detail(make_detail())

        self.assertEqual(
            self.model.skills,
            [
                {
                    "title": "Basic · Attack · Lv. 3",
                    "description": "Hits.",
                    "multipliers": [{"label": "Lv1", "value": "50%"}],
                }
            ],
        )
        self.assertEqual(
            self.model.extras,
            [
                {
                    "title": "Passives",
                    "entries": [{"name": "Trace", "text": "Body"}],
                }
            ],
        )

    def test_empty_build_removes_the_card(self):
        self.model.set_detail(make_detail())

        self.model.set_build([])

        self.assertEqual(self.model.buildState, "hidden")
        self.assertEqual(self.model.buildRows, [])

    def test_missing_art_url_reports_unavailable(self):
        self.model.set_detail(make_detail(art_url=""))

        self.assertEqual(self.model.artState, "unavailable")
        self.assertEqual(self.model.artMessage, "Art unavailable")
        self.assertEqual(self.model.artName, "Hero")

    def test_art_states_follow_the_source(self):
        self.model.set_detail(make_detail())
        self.assertEqual(self.model.artState, "hidden")

        self.model.show_art_skeleton()
        self.assertEqual(self.model.artState, "skeleton")

        self.model.set_art("image://nanokaart/1")
        self.assertEqual(self.model.artState, "ready")
        self.assertEqual(self.model.artSource, "image://nanokaart/1")

        self.model.set_art_unavailable()
        self.assertEqual(self.model.artState, "unavailable")
        self.assertEqual(self.model.artSource, "")

    def test_art_focus_defaults_to_centre_and_accepts_a_centroid(self):
        self.assertEqual(self.model.artFocusX, 0.5)

        self.model.set_art("image://nanokaart/1", 0.72)
        self.assertAlmostEqual(self.model.artFocusX, 0.72)

        self.model.set_art("image://nanokaart/1", 1.4)
        self.assertEqual(self.model.artFocusX, 1.0)

        self.model.set_art_unavailable()
        self.assertEqual(self.model.artFocusX, 0.5)

    def test_error_state_drops_the_content(self):
        self.model.set_detail(make_detail())
        self.model.set_error("nanoka has no page for this character yet")

        self.assertEqual(self.model.state, "error")
        self.assertEqual(
            self.model.errorMessage, "nanoka has no page for this character yet"
        )
        self.assertEqual(self.model.name, "")
        self.assertEqual(self.model.statRows, [])
        self.assertEqual(self.model.buildState, "hidden")
        self.assertEqual(self.model.artState, "unavailable")

    def test_loading_state_shows_the_skeletons(self):
        self.model.set_detail(make_detail())
        self.model.show_loading()

        self.assertEqual(self.model.state, "loading")
        self.assertEqual(self.model.artState, "skeleton")
        self.assertEqual(self.model.name, "")
        self.assertFalse(self.model.hasOverview)

    def test_buttons_emit_requests(self):
        closed = []
        retried = []
        self.model.closeRequested.connect(lambda: closed.append(1))
        self.model.retryRequested.connect(lambda: retried.append(1))

        self.model.requestClose()
        self.model.requestRetry()

        self.assertEqual(closed, [1])
        self.assertEqual(retried, [1])


if __name__ == "__main__":
    unittest.main()
