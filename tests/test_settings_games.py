"""Tests for the Games settings tab: toggling games and reordering sections."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QFrame, QMainWindow, QWidget
from support import QtTestCase, flush

import nanoka_viewer.ui.settings as settings_ui
from nanoka_viewer.api import GAMES


class SettingsGamesTabTests(QtTestCase):
    def setUp(self):
        super().setUp()
        self.settings = {"game_order": list(GAMES), "disabled_games": []}
        self.saved = []

        self.window = QMainWindow()
        self.central = QWidget()
        self.central.setObjectName("centralWidget")
        self.window.setCentralWidget(self.central)
        self.window.resize(900, 700)
        self.window.show()
        self.track_window(self.window)

        self._patches = [
            patch.object(settings_ui, "load_settings", side_effect=self._load),
            patch.object(settings_ui, "save_settings", side_effect=self._save),
            patch.object(settings_ui, "cache_sizes", return_value={}),
            patch.object(
                settings_ui, "read_build_cache_info", return_value={"last_cached": 0}
            ),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.popup = settings_ui.SettingsPopup(self.central)
        self.addCleanup(self._destroy_popup)
        self.changes = []
        self.popup.games_changed.connect(lambda: self.changes.append(True))
        self.popup.open_popup()
        flush()

    def _load(self):
        return dict(self.settings)

    def _save(self, settings):
        self.settings = dict(settings)
        self.saved.append(dict(settings))
        return settings

    def _destroy_popup(self):
        try:
            self.popup.close_popup()
            self.popup.deleteLater()
        except RuntimeError:
            pass
        flush()

    def test_cache_tab_is_the_default(self):
        self.assertEqual(self.popup.tabs.currentIndex(), 0)
        self.assertEqual(self.popup.tabs.tabText(0), "Cache")
        self.assertEqual(self.popup.tabs.tabText(1), "Games")

    def test_settings_use_form_cards_and_row_separators(self):
        cards = self.popup.findChildren(QFrame, "settingsCard")
        separators = self.popup.findChildren(QFrame, "settingsRowSeparator")

        self.assertGreaterEqual(len(cards), 2)
        self.assertGreaterEqual(len(separators), 2)

    def test_all_games_are_checked_by_default(self):
        for game in GAMES:
            self.assertTrue(self.popup.game_checkboxes[game].isChecked(), game)

    def test_every_game_is_available_in_the_order_list(self):
        self.assertEqual(self.popup.visible_game_order(), list(GAMES))

    def test_unchecking_hides_a_game_from_view_order(self):
        self.popup.game_checkboxes["hsr"].setChecked(False)
        flush()

        self.assertNotIn("hsr", self.popup.visible_game_order())
        self.assertEqual(self.settings["disabled_games"], ["hsr"])
        self.assertEqual(self.changes, [True])

    def test_rechecking_restores_the_stored_position(self):
        self.popup.game_checkboxes["hsr"].setChecked(False)
        self.popup.game_checkboxes["hsr"].setChecked(True)
        flush()

        self.assertEqual(self.popup.visible_game_order(), list(GAMES))
        self.assertEqual(self.settings["disabled_games"], [])

    def test_disabled_games_are_not_shown_after_reopen(self):
        self.settings = {
            "game_order": list(GAMES),
            "disabled_games": ["gi", "nte"],
        }
        self.popup.open_popup()
        flush()

        visible = self.popup.visible_game_order()
        self.assertNotIn("gi", visible)
        self.assertNotIn("nte", visible)
        self.assertFalse(self.popup.game_checkboxes["gi"].isChecked())
        self.assertFalse(self.popup.game_checkboxes["nte"].isChecked())

    def test_reordering_updates_only_enabled_slots(self):
        self.settings = {
            "game_order": ["zzz", "hsr", "gi", "ww", "nte"],
            "disabled_games": ["hsr"],
        }
        self.popup.open_popup()
        flush()
        # Enabled view: zzz, gi, ww, nte. Move nte to the front.
        item = self.popup.game_order_list.takeItem(3)
        self.popup.game_order_list.insertItem(0, item)
        self.popup._on_game_order_changed()

        self.assertEqual(self.settings["game_order"], ["nte", "hsr", "zzz", "gi", "ww"])
        self.assertEqual(self.settings["disabled_games"], ["hsr"])

    def test_cache_save_keeps_game_settings(self):
        self.popup.game_checkboxes["ww"].setChecked(False)
        flush()
        self.saved.clear()

        self.popup.cache_details.setChecked(False)
        flush()

        self.assertEqual(self.saved[-1]["disabled_games"], ["ww"])
        self.assertFalse(self.saved[-1]["cache_character_details"])


if __name__ == "__main__":
    unittest.main()
