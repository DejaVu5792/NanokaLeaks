"""Tests that Games-tab settings drive which sections are created and loaded."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from support import QtTestCase, find_qml_item, real_viewer, wait_for

from nanoka_viewer.api import GAMES
from nanoka_viewer.ui import main_window


class GameViewSettingsTests(QtTestCase):
    @staticmethod
    def _layout_games(window):
        return window.sections_model.games()

    @staticmethod
    def _wait_for_idle(window, timeout=2000):
        wait_for(
            lambda: window.reloadEnabled,
            timeout=timeout,
            message="window did not finish loading",
        )

    def test_only_enabled_games_get_sections_and_are_loaded(self):
        with real_viewer(with_card=False, games=["hsr"]) as (window, _):
            self._wait_for_idle(window)

            self.assertEqual(self._layout_games(window), ["hsr"])
            self.assertIsNotNone(window.sections_model.section("hsr"))

    def test_disabled_games_are_not_requested(self):
        requested = []
        with real_viewer(with_card=False, games=["hsr"]) as (window, _):
            from nanoka_viewer.ui import loader

            self._wait_for_idle(window)
            original = loader.get_all_characters_with_new_status
            loader.get_all_characters_with_new_status = lambda game: (
                requested.append(game) or []
            )
            try:
                window.load_data()
                self._wait_for_idle(window)
            finally:
                loader.get_all_characters_with_new_status = original

        self.assertEqual(requested, ["hsr"])

    def test_configured_order_is_applied_to_the_layout(self):
        with real_viewer(with_card=False, games=["ww", "hsr"]) as (window, _):
            self._wait_for_idle(window)

            self.assertEqual(self._layout_games(window), ["ww", "hsr"])

    def test_reordering_live_sections_does_not_reload(self):
        with real_viewer(with_card=False) as (window, _):
            self._wait_for_idle(window)
            generation = window._load_generation
            before = {
                game: window.sections_model.section(game) for game in GAMES
            }

            with patch.object(
                main_window, "get_enabled_games", return_value=list(reversed(GAMES))
            ):
                window.apply_game_settings()
            self._wait_for_idle(window)

            self.assertEqual(self._layout_games(window), list(reversed(GAMES)))
            self.assertEqual(window._load_generation, generation)
            self.assertFalse(window._load_in_progress)
            for game, section in before.items():
                self.assertIs(
                    window.sections_model.section(game),
                    section,
                    "reordering must keep the existing section (and its cards)",
                )

    def test_disabling_a_game_live_removes_its_section(self):
        with real_viewer(with_card=False) as (window, _):
            self._wait_for_idle(window)
            self.assertIsNotNone(window.sections_model.section("gi"))

            with patch.object(main_window, "get_enabled_games", return_value=["hsr"]):
                window.apply_game_settings()
            self._wait_for_idle(window)

            self.assertIsNone(window.sections_model.section("gi"))
            self.assertEqual(self._layout_games(window), ["hsr"])

    def test_a_lone_section_keeps_its_natural_height(self):
        with real_viewer(with_card=False, games=["hsr"]) as (window, _):
            self._wait_for_idle(window)
            section_list = find_qml_item(window.qml_root(), "sectionList")

            self.assertEqual(self._layout_games(window), ["hsr"])
            self.assertLess(
                section_list.property("contentHeight"),
                section_list.property("height"),
                "a lone section must not stretch to fill the list",
            )

    def test_no_enabled_games_shows_a_hint(self):
        with real_viewer(with_card=False, games=[]) as (window, _):
            self.assertEqual(self._layout_games(window), [])
            self.assertEqual(window.statusText, "No games enabled")
            self.assertTrue(window.reloadEnabled)


if __name__ == "__main__":
    unittest.main()
