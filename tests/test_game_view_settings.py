"""Tests that Games-tab settings drive which sections are created and loaded."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import support
from support import QtTestCase, real_viewer

from nanoka_viewer.api import GAMES
from nanoka_viewer.ui import main_window
from nanoka_viewer.ui.section import GameSection


class GameViewSettingsTests(QtTestCase):
    @staticmethod
    def _layout_games(window):
        by_section = {section: game for game, section in window.game_sections.items()}
        games = []
        for index in range(window.content_layout.count()):
            widget = window.content_layout.itemAt(index).widget()
            if isinstance(widget, GameSection):
                games.append(by_section[widget])
        return games

    @staticmethod
    def _wait_for_idle(window, timeout=2000):
        elapsed = 0
        while not window.refresh_btn.isEnabled():
            support.wait(10)
            elapsed += 10
            if elapsed >= timeout:
                raise AssertionError("window did not finish loading")

    def test_only_enabled_games_get_sections_and_are_loaded(self):
        with real_viewer(with_card=False, games=["hsr"]) as (window, _):
            self._wait_for_idle(window)

            self.assertEqual(list(window.game_sections), ["hsr"])
            self.assertEqual(self._layout_games(window), ["hsr"])

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

            with patch.object(
                main_window, "get_enabled_games", return_value=list(reversed(GAMES))
            ):
                window.apply_game_settings()
            support.flush()

            self.assertEqual(self._layout_games(window), list(reversed(GAMES)))
            self.assertEqual(window._load_generation, generation)
            self.assertFalse(window._load_in_progress)

    def test_disabling_a_game_live_removes_its_section(self):
        with real_viewer(with_card=False) as (window, _):
            self._wait_for_idle(window)
            self.assertIn("gi", window.game_sections)

            with patch.object(main_window, "get_enabled_games", return_value=["hsr"]):
                window.apply_game_settings()
            support.flush()

            self.assertNotIn("gi", window.game_sections)
            self.assertEqual(list(window.game_sections), ["hsr"])

    def test_single_remaining_section_keeps_its_natural_height(self):
        with real_viewer(with_card=False) as (window, _):
            self._wait_for_idle(window)

            with patch.object(
                main_window, "get_enabled_games", return_value=["zzz"]
            ):
                window.apply_game_settings()
            self._wait_for_idle(window)
            support.flush()

            section = window.game_sections["zzz"]
            self.assertEqual(list(window.game_sections), ["zzz"])
            self.assertEqual(
                section.height(),
                section.sizeHint().height(),
                "a lone section must not stretch to fill the scroll area",
            )

    def test_no_enabled_games_shows_a_hint(self):
        with real_viewer(with_card=False, games=[]) as (window, _):
            self.assertEqual(list(window.game_sections), [])
            self.assertEqual(window.status_label.text(), "No games enabled")
            self.assertTrue(window.refresh_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
