"""Back navigation for rule-term jumps in the details pane.

Clicking a rule-term link used to scroll the pane to the Rule Terms card with
no way back.  The panel now remembers the scroll offset before each jump: the
header shows a Back button, and Alt+Left performs the same action.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

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
from nanoka_viewer.api.detail_models import ContentEntry, SkillDetail

TIMEOUT = 4000
TERM_ID = "term-1"
TERM_NAME = "Gradient Beacon"
TERM_BODY = "A beacon that keeps the area lit for a short while."


class RuleTermNavigationTests(QtTestCase):
    def _open(self):
        detail = replace(
            SAMPLE_DETAIL,
            overview=f'<a href="term:{TERM_ID}">{TERM_NAME}</a> is a rule term.',
            # Enough collapsed skills to make the pane scrollable, so a term
            # jump has somewhere to go and a meaningful position to return to.
            skills=[
                SkillDetail(f"Skill {index}", "Attack", "Body", [], 1)
                for index in range(20)
            ],
            terms=[ContentEntry(TERM_NAME, TERM_BODY, TERM_ID)],
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

    def _activate_term(self, popup):
        """Follow the overview's rule-term anchor like a real link click."""
        overview = self._find(popup, "detailsOverview")
        overview.linkActivated.emit(f"term:{TERM_ID}")
        flush()
        wait(40)

    def test_back_button_returns_to_the_scroll_position_before_the_jump(self):
        popup = self._open()
        scroll = self._find(popup, "detailsScroll")
        back = self._find(popup, "detailsBackButton")

        self.assertFalse(
            back.isVisible(),
            "the Back button must stay hidden until a term jump is recorded",
        )

        scroll.setProperty("contentY", 120.0)
        flush()
        self._activate_term(popup)

        jumped = scroll.property("contentY")
        self.assertGreater(jumped, 120.0, "the link must scroll to the term")
        self.assertTrue(back.isVisible())

        click_qml(popup._qml, back)
        flush()
        self.assertAlmostEqual(
            scroll.property("contentY"),
            120.0,
            delta=0.5,
            msg="Back must restore the exact pre-jump scroll offset",
        )
        self.assertFalse(back.isVisible())

    def test_alt_left_returns_to_the_previous_scroll_position(self):
        popup = self._open()
        scroll = self._find(popup, "detailsScroll")
        back = self._find(popup, "detailsBackButton")

        scroll.setProperty("contentY", 80.0)
        flush()
        self._activate_term(popup)
        self.assertTrue(back.isVisible())

        popup._qml.setFocus()
        QTest.keyClick(
            popup._qml,
            Qt.Key.Key_Left,
            Qt.KeyboardModifier.AltModifier,
        )
        flush()
        wait(40)

        self.assertAlmostEqual(scroll.property("contentY"), 80.0, delta=0.5)
        self.assertFalse(back.isVisible())

    def test_repeated_jumps_stack_and_unwind_one_at_a_time(self):
        popup = self._open()
        scroll = self._find(popup, "detailsScroll")
        back = self._find(popup, "detailsBackButton")

        self._activate_term(popup)
        first_jump = scroll.property("contentY")

        # Scroll somewhere else, then follow the same link again: that is a
        # new jump, so Back has to return to this manual position first.
        scroll.setProperty("contentY", 300.0)
        flush()
        self._activate_term(popup)
        self.assertAlmostEqual(scroll.property("contentY"), first_jump, delta=0.5)

        click_qml(popup._qml, back)
        flush()
        self.assertAlmostEqual(scroll.property("contentY"), 300.0, delta=0.5)
        self.assertTrue(back.isVisible(), "one older jump must remain")

        click_qml(popup._qml, back)
        flush()
        self.assertAlmostEqual(scroll.property("contentY"), 0.0, delta=0.5)
        self.assertFalse(back.isVisible())


if __name__ == "__main__":
    unittest.main()
