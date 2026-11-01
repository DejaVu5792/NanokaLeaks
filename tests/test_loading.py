"""Regression tests for progressive card loading and reload races.

The cards are QML delegates now, but the state machine that feeds them is
still Python: batches of ten are appended to the section's
:class:`CharacterModel`, a superseded load cannot append anything, and the
header only leaves its "Loading..." state once every section is complete.
"""

from __future__ import annotations

import unittest

from support import QtTestCase, real_viewer, wait, wait_for

_HSR_CHAR = {
    "en": "Testchar",
    "rank": 5,
    "damageType": "Physical",
    "baseType": "Warrior",
    "icon": "TestIcon",
    "release": None,
}


class BatchLoadingTests(QtTestCase):
    def _wait_for_idle(self, window, timeout=2000):
        wait_for(
            lambda: window.reloadEnabled,
            timeout=timeout,
            message="window did not finish loading",
        )

    def test_cards_are_appended_in_batches_of_ten(self):
        with real_viewer(with_card=False, games=["hsr"]) as (window, _):
            self._wait_for_idle(window)
            section = window.sections_model.section("hsr")
            chars = [(f"id{index}", _HSR_CHAR, False) for index in range(25)]
            section.characters.clear()
            window._loading_chars["hsr"] = list(chars)
            window._loading_index["hsr"] = 0

            window._load_next_batch("hsr", chars, window._load_generation)
            self.assertEqual(
                section.characters.rowCount(),
                10,
                "one batch must be appended per event-loop turn",
            )

            wait_for(
                lambda: section.characters.rowCount() == 25,
                message="the remaining batches were never appended",
            )
            self.assertEqual(section.characters.char_ids(), [c[0] for c in chars])
            self.assertEqual(section.status, "25 total")

    def test_reload_replaces_cards_instead_of_appending(self):
        with real_viewer(with_card=False, games=["hsr"]) as (window, _):
            self._wait_for_idle(window)
            section = window.sections_model.section("hsr")
            self.assertEqual(section.characters.char_ids(), ["1001"])

            window.load_data()
            self._wait_for_idle(window)
            self.assertEqual(section.characters.char_ids(), ["1001"])


class ReloadRaceTests(QtTestCase):
    def _wait_for_idle(self, window, timeout=2000):
        wait_for(
            lambda: window.reloadEnabled,
            timeout=timeout,
            message="window did not finish loading",
        )

    def test_reload_is_ignored_while_a_load_is_active(self):
        with real_viewer(games=["hsr"]) as (window, card):
            self.assertIsNotNone(card)
            self._wait_for_idle(window)

            window.load_data()
            first_thread = window.load_thread
            self.assertFalse(window.reloadEnabled)
            self.assertEqual(window.reloadText, "Loading...")

            window.load_data()
            self.assertIs(
                window.load_thread,
                first_thread,
                "a second Reload must not start another load",
            )

            self._wait_for_idle(window)
            self.assertEqual(window.reloadText, "Reload")
            self.assertEqual(
                window.sections_model.section("hsr").characters.rowCount(),
                1,
                "spamming Reload must not duplicate cards",
            )

    def test_stale_generation_cannot_add_cards(self):
        with real_viewer(games=["hsr"]) as (window, card):
            self.assertIsNotNone(card)
            self._wait_for_idle(window)
            window.load_data()
            stale_generation = window._load_generation - 1

            window.on_game_loaded(
                "hsr",
                [("9999", _HSR_CHAR, False)],
                stale_generation,
            )
            wait(30)

            char_ids = window.sections_model.section("hsr").characters.char_ids()
            self.assertNotIn("9999", char_ids)

    def test_reload_only_enables_refresh_after_cards_are_built(self):
        with real_viewer(games=["hsr"]) as (window, card):
            self.assertIsNotNone(card)
            window._set_reload(enabled=False)
            window._pending_sections = {"hsr"}
            window._fetch_finished = True

            window._mark_section_done("other")
            self.assertFalse(window.reloadEnabled)

            window._mark_section_done("hsr")
            self.assertTrue(window.reloadEnabled)
            self.assertEqual(window.reloadText, "Reload")


if __name__ == "__main__":
    unittest.main()
