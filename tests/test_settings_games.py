"""Tests for the Games settings tab: toggling games and reordering sections."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFrame, QMainWindow, QStyle, QStyleOption, QWidget
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
        self.assertEqual(self.popup.tabs.tabText(1), "View")

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

    def test_toggle_rows_show_right_aligned_character_counts(self):
        label = self.popup.game_count_labels["zzz"]
        self.assertEqual(label.text(), "1,234 characters")
        self.assertTrue(label.alignment() & Qt.AlignmentFlag.AlignRight)

        # Games without cached data show a placeholder instead of fetching.
        self.assertEqual(self.popup.game_count_labels["gi"].text(), "\u2014")

    def test_clicking_a_toggle_row_toggles_the_game(self):
        self.popup.tabs.setCurrentIndex(1)
        flush()
        row = self.popup.game_rows["hsr"]

        QTest.mouseClick(
            row,
            Qt.MouseButton.LeftButton,
            pos=QPoint(row.width() - 12, row.height() // 2),
        )
        flush()

        self.assertFalse(self.popup.game_checkboxes["hsr"].isChecked())
        self.assertEqual(self.settings["disabled_games"], ["hsr"])
        self.assertNotIn("hsr", self.popup.visible_game_order())

    def test_toggle_reset_enables_every_game(self):
        self.popup.game_checkboxes["gi"].setChecked(False)
        self.popup.game_checkboxes["ww"].setChecked(False)
        flush()
        self.saved.clear()
        self.changes.clear()

        self.popup.section_resets["Toggle View"].click()
        flush()

        self.assertTrue(
            all(box.isChecked() for box in self.popup.game_checkboxes.values())
        )
        self.assertEqual(self.settings["disabled_games"], [])
        self.assertEqual(self.popup.visible_game_order(), list(GAMES))
        self.assertEqual(self.saved[-1]["disabled_games"], [])
        self.assertEqual(self.changes, [True])

    def test_order_reset_restores_the_default_order(self):
        item = self.popup.game_order_list.takeItem(4)
        self.popup.game_order_list.insertItem(0, item)
        self.popup._on_game_order_changed()
        self.assertEqual(self.popup.visible_game_order()[0], "nte")

        self.popup.section_resets["View Order"].click()
        flush()

        self.assertEqual(self.popup.visible_game_order(), list(GAMES))
        self.assertEqual(self.settings["game_order"], list(GAMES))

    def test_cache_reset_restores_the_default_options(self):
        self.popup.tabs.setCurrentIndex(0)
        self.popup.cache_details.setChecked(False)
        self.popup.cache_builds.setChecked(False)
        flush()
        self.saved.clear()

        self.popup.section_resets["Caching"].click()
        flush()

        self.assertTrue(self.popup.cache_details.isChecked())
        self.assertTrue(self.popup.cache_builds.isChecked())
        self.assertTrue(self.popup.cache_artwork.isChecked())
        self.assertTrue(self.saved[-1]["cache_character_details"])
        self.assertTrue(self.saved[-1]["cache_character_builds"])

    def test_view_order_uses_the_compact_drag_handle(self):
        first = self.popup.game_order_list.item(0)
        self.assertTrue(first.text().startswith("\u28ff"))

    def test_view_order_fits_every_row_without_an_inner_scrollbar(self):
        order_list = self.popup.game_order_list
        self.assertEqual(
            order_list.verticalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.assertGreaterEqual(
            order_list.minimumHeight(),
            order_list.count() * order_list.sizeHintForRow(0),
        )

    def test_drag_pixmap_uses_partial_transparency(self):
        order_list = self.popup.game_order_list
        order_list.setCurrentRow(0)
        captured = {}

        class FakeDrag:
            def __init__(self, source):
                pass

            def setMimeData(self, mime):
                captured["mime"] = mime

            def setPixmap(self, pixmap):
                captured["pixmap"] = pixmap

            def setHotSpot(self, point):
                captured["hotspot"] = point

            def exec(self, actions):
                return Qt.DropAction.IgnoreAction

        with patch.object(settings_ui, "QDrag", FakeDrag):
            order_list.startDrag(Qt.DropAction.MoveAction)

        pixmap = captured["pixmap"]
        image = pixmap.toImage()
        self.assertTrue(image.hasAlphaChannel())
        alpha = image.pixelColor(image.width() // 2, image.height() // 2).alpha()
        self.assertGreaterEqual(alpha, 80)
        self.assertLessEqual(alpha, 120)  # about 40% opacity
        self.assertTrue(
            captured["mime"].hasFormat("application/x-qabstractitemmodeldatalist")
        )

    def test_drop_indicator_is_four_pixels_thick(self):
        order_list = self.popup.game_order_list
        option = QStyleOption()
        option.rect = QRect(0, 40, 180, 2)
        option.palette = order_list.palette()

        image = QImage(180, 80, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        order_list.style().drawPrimitive(
            QStyle.PrimitiveElement.PE_IndicatorItemViewItemDrop,
            option,
            painter,
            order_list,
        )
        painter.end()

        background = image.pixelColor(10, 0)
        painted = [y for y in range(80) if image.pixelColor(10, y) != background]
        self.assertEqual(len(painted), 4)
        self.assertIn(40, painted)


if __name__ == "__main__":
    unittest.main()
