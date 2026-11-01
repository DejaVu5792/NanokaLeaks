"""Tests for the View settings tab: toggling games and reordering sections."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QMainWindow, QWidget

import nanoka_viewer.ui.settings as settings_ui
from nanoka_viewer.api import GAMES
from support import (
    QtTestCase,
    click_qml,
    drag_qml,
    find_qml_item,
    find_qml_items,
    flush,
    move_qml,
    press_qml,
    release_qml,
    wait,
)


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
            patch.object(
                settings_ui,
                "cached_character_count",
                side_effect=lambda game: {"zzz": 1234, "hsr": 40}.get(game),
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
        wait(120)

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

    @property
    def model(self):
        return self.popup._model

    def _qml(self, name):
        item = find_qml_item(self.popup._qml.rootObject(), name)
        self.assertIsNotNone(item, f"{name} was not created")
        return item

    def _view_tab(self):
        """Switch to the View tab so its rows can be clicked."""
        self.model.setTab(1)
        flush()
        wait(80)

    # -- layout ------------------------------------------------------------

    def test_cache_tab_is_the_default(self):
        self.assertEqual(self.model.tabIndex, 0)

        cache_tab = self._qml("settingsTabCache")
        view_tab = self._qml("settingsTabView")
        self.assertEqual(cache_tab.property("text"), "Cache")
        self.assertEqual(view_tab.property("text"), "View")

    def test_clicking_a_tab_switches_the_page(self):
        click_qml(self.popup._qml, self._qml("settingsTabView"))

        self.assertEqual(self.model.tabIndex, 1)
        self.assertTrue(self._qml("settingsViewPage").property("visible"))
        self.assertFalse(self._qml("settingsCachePage").property("visible"))

    def test_settings_use_form_cards_and_row_separators(self):
        root = self.popup._qml.rootObject()
        cards = find_qml_items(root, "settingsCard")
        separators = find_qml_items(root, "settingsRowSeparator")

        self.assertGreaterEqual(len(cards), 2)
        self.assertGreaterEqual(len(separators), 2)

    # -- experimental ------------------------------------------------------

    def test_smart_centering_defaults_on_and_saves(self):
        self.assertTrue(self.model.srCentroid)

        self.model.setSrCentroid(False)

        self.assertFalse(self.settings["sr_centroid_centering"])

    def test_smart_centering_reset_restores_default(self):
        self.model.setSrCentroid(False)
        flush()

        self.model.resetSection("experimental")
        flush()

        self.assertTrue(self.model.srCentroid)
        self.assertTrue(self.settings["sr_centroid_centering"])

    # -- toggling games ----------------------------------------------------

    def test_all_games_are_checked_by_default(self):
        for game in GAMES:
            self.assertTrue(self.model.games.is_enabled(game), game)

    def test_every_game_is_available_in_the_order_list(self):
        self.assertEqual(self.popup.visible_game_order(), list(GAMES))

    def test_unchecking_hides_a_game_from_view_order(self):
        self.model.setGameEnabled("hsr", False)
        flush()

        self.assertNotIn("hsr", self.popup.visible_game_order())
        self.assertEqual(self.settings["disabled_games"], ["hsr"])
        self.assertEqual(self.changes, [True])

    def test_rechecking_restores_the_stored_position(self):
        self.model.setGameEnabled("hsr", False)
        self.model.setGameEnabled("hsr", True)
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
        self.assertFalse(self.model.games.is_enabled("gi"))
        self.assertFalse(self.model.games.is_enabled("nte"))

    def test_clicking_a_toggle_row_toggles_the_game(self):
        self._view_tab()

        click_qml(self.popup._qml, self._qml("gameToggleRow-hsr"))

        self.assertFalse(self.model.games.is_enabled("hsr"))
        self.assertEqual(self.settings["disabled_games"], ["hsr"])
        self.assertNotIn("hsr", self.popup.visible_game_order())

    def test_toggle_reset_enables_every_game(self):
        self.model.setGameEnabled("gi", False)
        self.model.setGameEnabled("ww", False)
        flush()
        self.saved.clear()
        self.changes.clear()
        self._view_tab()

        click_qml(self.popup._qml, self._qml("resetToggle"))

        for game in GAMES:
            self.assertTrue(self.model.games.is_enabled(game), game)
        self.assertEqual(self.settings["disabled_games"], [])
        self.assertEqual(self.popup.visible_game_order(), list(GAMES))
        self.assertEqual(self.saved[-1]["disabled_games"], [])
        self.assertEqual(self.changes, [True])

    # -- reordering --------------------------------------------------------

    def test_reordering_updates_only_enabled_slots(self):
        self.settings = {
            "game_order": ["zzz", "hsr", "gi", "ww", "nte"],
            "disabled_games": ["hsr"],
        }
        self.popup.open_popup()
        flush()
        # Enabled view: zzz, gi, ww, nte. Move nte to the front.
        self.model.moveGame(3, 0)
        flush()

        self.assertEqual(self.settings["game_order"], ["nte", "hsr", "zzz", "gi", "ww"])
        self.assertEqual(self.settings["disabled_games"], ["hsr"])

    def test_dragging_a_row_reorders_the_sections(self):
        self._view_tab()

        drag_qml(self.popup._qml, self._qml("gameOrderRow-zzz"), 2 * 34)

        self.assertEqual(
            self.popup.visible_game_order(), ["hsr", "gi", "zzz", "ww", "nte"]
        )
        self.assertEqual(
            self.settings["game_order"], ["hsr", "gi", "zzz", "ww", "nte"]
        )

    def test_dragging_does_nothing_without_moving(self):
        self._view_tab()

        row = self._qml("gameOrderRow-zzz")
        point = press_qml(self.popup._qml, row)
        release_qml(self.popup._qml, point)

        self.assertEqual(self.popup.visible_game_order(), list(GAMES))

    def test_dragging_a_row_does_not_scroll_the_page(self):
        self._view_tab()
        page = self._qml("settingsViewPage")

        drag_qml(self.popup._qml, self._qml("gameOrderRow-zzz"), 2 * 34)

        self.assertEqual(page.property("contentY"), 0)
        self.assertEqual(
            self.popup.visible_game_order(), ["hsr", "gi", "zzz", "ww", "nte"]
        )

    def test_order_rows_have_move_buttons_with_edge_rows_disabled(self):
        self._view_tab()
        order = list(GAMES)

        first = self._qml("gameOrderRow-" + order[0])
        self.assertIsNotNone(find_qml_item(first, "orderRowUp"))
        self.assertIsNotNone(find_qml_item(first, "orderRowDown"))
        self.assertFalse(find_qml_item(first, "orderRowUp").property("enabled"))
        self.assertTrue(find_qml_item(first, "orderRowDown").property("enabled"))

        last = self._qml("gameOrderRow-" + order[-1])
        self.assertTrue(find_qml_item(last, "orderRowUp").property("enabled"))
        self.assertFalse(find_qml_item(last, "orderRowDown").property("enabled"))

    def test_move_down_button_moves_the_row_one_slot(self):
        self._view_tab()
        row = self._qml("gameOrderRow-zzz")

        click_qml(self.popup._qml, find_qml_item(row, "orderRowDown"))

        expected = ["hsr", "zzz", "gi", "ww", "nte"]
        self.assertEqual(self.popup.visible_game_order(), expected)
        self.assertEqual(self.settings["game_order"], expected)

    def test_move_up_button_moves_the_row_one_slot(self):
        self._view_tab()
        row = self._qml("gameOrderRow-gi")

        click_qml(self.popup._qml, find_qml_item(row, "orderRowUp"))

        expected = ["zzz", "gi", "hsr", "ww", "nte"]
        self.assertEqual(self.popup.visible_game_order(), expected)
        self.assertEqual(self.settings["game_order"], expected)

    def test_move_buttons_keep_disabled_games_in_their_slots(self):
        self.settings = {
            "game_order": ["zzz", "hsr", "gi", "ww", "nte"],
            "disabled_games": ["hsr"],
        }
        self.popup.open_popup()
        flush()
        self._view_tab()

        row = self._qml("gameOrderRow-gi")
        click_qml(self.popup._qml, find_qml_item(row, "orderRowUp"))

        self.assertEqual(
            self.settings["game_order"], ["gi", "hsr", "zzz", "ww", "nte"]
        )
        self.assertEqual(self.settings["disabled_games"], ["hsr"])

    def test_order_reset_restores_the_default_order(self):
        self.model.moveGame(4, 0)
        self.assertEqual(self.popup.visible_game_order()[0], "nte")
        self._view_tab()

        click_qml(self.popup._qml, self._qml("resetOrder"))

        self.assertEqual(self.popup.visible_game_order(), list(GAMES))
        self.assertEqual(self.settings["game_order"], list(GAMES))

    def test_view_order_uses_the_compact_drag_handle(self):
        row = self._qml("gameOrderRow-zzz")
        label = find_qml_item(row, "orderRowLabel")

        self.assertIsNotNone(label)
        self.assertTrue(label.property("text").startswith("\u28ff"))

    def test_view_order_fits_every_row_without_an_inner_scrollbar(self):
        order_list = self._qml("gameOrderList")

        self.assertFalse(order_list.property("interactive"))
        self.assertGreaterEqual(order_list.height(), order_list.property("count") * 34)

    def test_drop_indicator_is_four_pixels_thick(self):
        indicator = self._qml("orderDropIndicator")

        self.assertEqual(indicator.height(), 4)
        highlight = self.application.palette().color(
            QPalette.ColorRole.Highlight
        )
        self.assertEqual(indicator.property("color").name(), highlight.name())

    def test_drop_indicator_only_shows_while_dragging(self):
        self._view_tab()
        indicator = self._qml("orderDropIndicator")
        self.assertFalse(indicator.property("visible"))

        row = self._qml("gameOrderRow-zzz")
        start = press_qml(self.popup._qml, row)
        move_qml(self.popup._qml, QPoint(start.x(), start.y() + 34))
        flush()

        self.assertTrue(indicator.property("visible"))
        release_qml(self.popup._qml, QPoint(start.x(), start.y() + 34))
        self.assertFalse(indicator.property("visible"))

    def test_dragging_shows_a_faded_ghost_of_the_row(self):
        self._view_tab()
        ghost = self._qml("orderDragGhost")
        self.assertFalse(ghost.property("visible"))

        row = self._qml("gameOrderRow-zzz")
        start = press_qml(self.popup._qml, row)
        move_qml(self.popup._qml, QPoint(start.x(), start.y() + 34))
        flush()

        self.assertTrue(ghost.property("visible"))
        self.assertAlmostEqual(ghost.property("opacity"), 0.4)
        self.assertIn(
            GAMES["zzz"]["name"],
            find_qml_item(ghost, "orderRowLabel").property("text"),
        )

        release_qml(self.popup._qml, QPoint(start.x(), start.y() + 34))
        self.assertFalse(ghost.property("visible"))

    def test_drag_ghost_follows_the_pointer(self):
        self._view_tab()
        ghost = self._qml("orderDragGhost")
        row = self._qml("gameOrderRow-zzz")

        start = press_qml(self.popup._qml, row)
        move_qml(self.popup._qml, QPoint(start.x(), start.y() + 34))
        flush()
        first = ghost.property("y")

        move_qml(self.popup._qml, QPoint(start.x(), start.y() + 68))
        flush()
        second = ghost.property("y")

        release_qml(self.popup._qml, QPoint(start.x(), start.y() + 68))
        self.assertAlmostEqual(second - first, 34)

    # -- other options -----------------------------------------------------

    def test_cache_save_keeps_game_settings(self):
        self.model.setGameEnabled("ww", False)
        flush()
        self.saved.clear()

        self.model.setCache("details", False)
        flush()

        self.assertEqual(self.saved[-1]["disabled_games"], ["ww"])
        self.assertFalse(self.saved[-1]["cache_character_details"])

    def test_toggle_rows_show_right_aligned_character_counts(self):
        root = self.popup._qml.rootObject()
        row = self._qml("gameToggleRow-zzz")
        label = find_qml_item(row, "settingsCount")

        self.assertIsNotNone(label)
        self.assertEqual(label.property("text"), "1,234 characters")

        # The count is the last item in the row layout, so a right-aligned
        # label ends at the row's right edge minus the 8px row margin.
        row_right = row.mapToItem(root, row.width(), 0).x()
        label_right = label.mapToItem(root, label.width(), 0).x()
        self.assertAlmostEqual(label_right, row_right - 8, delta=2)

        # Games without cached data show a placeholder instead of fetching.
        self.assertEqual(self.model.games.count_text("gi"), "\u2014")

    def test_cache_reset_restores_the_default_options(self):
        self.model.setTab(0)
        self.model.setCache("details", False)
        self.model.setCache("builds", False)
        flush()
        self.saved.clear()

        self.model.resetSection("caching")
        flush()

        self.assertTrue(self.model.cacheDetails)
        self.assertTrue(self.model.cacheBuilds)
        self.assertTrue(self.model.cacheArtwork)
        self.assertTrue(self.saved[-1]["cache_character_details"])
        self.assertTrue(self.saved[-1]["cache_character_builds"])


if __name__ == "__main__":
    unittest.main()
