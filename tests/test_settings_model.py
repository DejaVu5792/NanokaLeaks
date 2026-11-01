"""Tests for the settings view models (no QML engine involved)."""

from __future__ import annotations

import unittest

from PySide6.QtCore import QModelIndex

from nanoka_viewer.ui.settings_model import (
    CACHE_KINDS,
    GameOrderModel,
    GameToggleModel,
    SettingsViewModel,
    TAB_CACHE,
    TAB_VIEW,
)
from support import app


class Spy:
    """Collect the arguments of every signal emission."""

    def __init__(self, signal):
        self.calls = []
        signal.connect(self._record)

    def _record(self, *args):
        self.calls.append(args)

    def __len__(self):
        return len(self.calls)


GAMES = [("zzz", "Zenless Zone Zero", True), ("hsr", "Honkai: Star Rail", True)]


class GameToggleModelTests(unittest.TestCase):
    def setUp(self):
        app()
        self.model = GameToggleModel()
        self.model.reset_rows(GAMES)

    def test_reset_rows_populates_every_role(self):
        self.assertEqual(self.model.rowCount(), 2)
        first = self.model.index(0, 0)
        self.assertEqual(self.model.data(first, self.model.GameIdRole), "zzz")
        self.assertEqual(
            self.model.data(first, self.model.NameRole), "Zenless Zone Zero"
        )
        self.assertIs(self.model.data(first, self.model.EnabledRole), True)
        self.assertEqual(self.model.data(first, self.model.CountRole), "")
        self.assertEqual(self.model.games(), ["zzz", "hsr"])

    def test_invalid_indexes_have_no_data(self):
        self.assertIsNone(self.model.data(QModelIndex()))
        self.assertIsNone(self.model.data(self.model.index(9, 0)))
        self.assertEqual(self.model.rowCount(self.model.index(0, 0)), 0)

    def test_role_names_match_the_qml_roles(self):
        names = {bytes(value) for value in self.model.roleNames().values()}
        self.assertEqual(
            names,
            {b"gameId", b"name", b"gameEnabled", b"countText", b"countTooltip"},
        )

    def test_set_enabled_emits_data_changed(self):
        spy = Spy(self.model.dataChanged)

        self.model.set_enabled("hsr", False)

        self.assertFalse(self.model.is_enabled("hsr"))
        self.assertEqual(len(spy), 1)
        top_left, bottom_right, roles = spy.calls[0]
        self.assertEqual(top_left.row(), 1)
        self.assertEqual(bottom_right.row(), 1)
        self.assertEqual(roles, [self.model.EnabledRole])

    def test_set_enabled_is_a_no_op_for_same_or_unknown_games(self):
        spy = Spy(self.model.dataChanged)

        self.model.set_enabled("zzz", True)
        self.model.set_enabled("nope", False)

        self.assertEqual(len(spy), 0)
        self.assertFalse(self.model.is_enabled("nope"))

    def test_set_all_enabled_bursts_once(self):
        self.model.set_enabled("zzz", False)
        spy = Spy(self.model.dataChanged)

        self.model.set_all_enabled(True)

        self.assertTrue(all(self.model.enabled_games().values()))
        self.assertEqual(len(spy), 1)
        top_left, bottom_right, _roles = spy.calls[0]
        self.assertEqual((top_left.row(), bottom_right.row()), (0, 1))

    def test_set_counts_fills_text_and_tooltip(self):
        self.model.set_counts({"zzz": ("1,234 characters", "1,234 cached")})

        self.assertEqual(self.model.count_text("zzz"), "1,234 characters")
        self.assertEqual(self.model.count_tooltip("zzz"), "1,234 cached")
        self.assertEqual(self.model.count_text("hsr"), "")

    def test_enabled_games_maps_every_row(self):
        self.model.set_enabled("zzz", False)

        self.assertEqual(
            self.model.enabled_games(), {"zzz": False, "hsr": True}
        )


class GameOrderModelTests(unittest.TestCase):
    def setUp(self):
        app()
        self.model = GameOrderModel()
        self.model.reset_games(
            ["zzz", "hsr", "gi"],
            {"zzz": "Zenless Zone Zero", "hsr": "Honkai: Star Rail"},
        )

    def test_reset_games_populates_every_role(self):
        self.assertEqual(self.model.rowCount(), 3)
        self.assertEqual(self.model.games(), ["zzz", "hsr", "gi"])
        first = self.model.index(0, 0)
        self.assertEqual(self.model.data(first, self.model.GameIdRole), "zzz")
        self.assertEqual(
            self.model.data(first, self.model.GameNameRole), "Zenless Zone Zero"
        )
        # Unknown games fall back to their id.
        third = self.model.index(2, 0)
        self.assertEqual(self.model.data(third, self.model.GameNameRole), "gi")

    def test_invalid_indexes_have_no_data(self):
        self.assertIsNone(self.model.data(QModelIndex()))
        self.assertIsNone(self.model.data(self.model.index(9, 0)))

    def test_move_down_splices_the_row(self):
        spy = Spy(self.model.rowsMoved)

        self.assertTrue(self.model.move(0, 2))

        self.assertEqual(self.model.games(), ["hsr", "gi", "zzz"])
        self.assertEqual(len(spy), 1)

    def test_move_up_splices_the_row(self):
        self.assertTrue(self.model.move(2, 0))

        self.assertEqual(self.model.games(), ["gi", "zzz", "hsr"])

    def test_move_rejects_invalid_indexes(self):
        spy = Spy(self.model.rowsMoved)

        self.assertFalse(self.model.move(1, 1))
        self.assertFalse(self.model.move(0, 5))
        self.assertFalse(self.model.move(-1, 0))

        self.assertEqual(self.model.games(), ["zzz", "hsr", "gi"])
        self.assertEqual(len(spy), 0)


class SettingsViewModelTests(unittest.TestCase):
    def setUp(self):
        app()
        self.model = SettingsViewModel()

    def test_tab_starts_on_cache_and_clamps_unknown_indexes(self):
        spy = Spy(self.model.tabChanged)
        self.assertEqual(self.model.tabIndex, TAB_CACHE)

        self.model.setTab(TAB_VIEW)
        self.assertEqual(self.model.tabIndex, TAB_VIEW)
        self.assertEqual(len(spy), 1)

        self.model.setTab(7)
        self.assertEqual(self.model.tabIndex, TAB_CACHE)
        self.assertEqual(len(spy), 2)

    def test_set_tab_is_a_no_op_for_the_current_tab(self):
        spy = Spy(self.model.tabChanged)

        self.model.setTab(TAB_CACHE)

        self.assertEqual(len(spy), 0)

    def test_cache_flags_start_enabled(self):
        self.assertEqual(self.model.cache_flags(), {k: True for k in CACHE_KINDS})
        self.assertTrue(self.model.cacheEnabled)

    def test_set_cache_emits_both_signals(self):
        changed = Spy(self.model.cacheChanged)
        setting = Spy(self.model.cacheSettingChanged)

        self.model.setCache("artwork", False)

        self.assertFalse(self.model.cacheArtwork)
        self.assertEqual(len(changed), 1)
        self.assertEqual(setting.calls, [("artwork", False)])

    def test_set_cache_is_a_no_op_for_the_same_value(self):
        setting = Spy(self.model.cacheSettingChanged)

        self.model.setCache("details", True)

        self.assertEqual(len(setting), 0)

    def test_set_cache_flags_never_emits_an_action(self):
        changed = Spy(self.model.cacheChanged)
        setting = Spy(self.model.cacheSettingChanged)

        self.model.set_cache_flags(details=False, builds=True, artwork=False)

        self.assertEqual(
            self.model.cache_flags(),
            {"details": False, "builds": True, "artwork": False},
        )
        self.assertEqual(len(changed), 1)
        self.assertEqual(len(setting), 0)

    def test_cache_enabled_tracks_the_preload_state(self):
        spy = Spy(self.model.cacheChanged)

        self.model.set_cache_enabled(False)

        self.assertFalse(self.model.cacheEnabled)
        self.assertEqual(len(spy), 1)

        self.model.set_cache_enabled(False)
        self.assertEqual(len(spy), 1)

    def test_experimental_defaults_on(self):
        self.assertTrue(self.model.srCentroid)

    def test_set_experimental_never_emits_an_action(self):
        changed = Spy(self.model.experimentalChanged)
        setting = Spy(self.model.experimentalSettingChanged)

        self.model.set_experimental(False)

        self.assertFalse(self.model.srCentroid)
        self.assertEqual(len(changed), 1)
        self.assertEqual(len(setting), 0)

    def test_set_sr_centroid_emits_both_signals(self):
        changed = Spy(self.model.experimentalChanged)
        setting = Spy(self.model.experimentalSettingChanged)

        self.model.setSrCentroid(False)

        self.assertFalse(self.model.srCentroid)
        self.assertEqual(len(changed), 1)
        self.assertEqual(setting.calls, [(False,)])

        self.model.setSrCentroid(False)
        self.assertEqual(len(setting), 1)

    def test_cache_meta_updates_in_one_burst(self):
        spy = Spy(self.model.cacheMetaChanged)

        self.model.set_cache_meta(
            details="2 kB", builds="3 kB", artwork="5 kB", last_cached="never"
        )

        self.assertEqual(self.model.detailsSize, "2 kB")
        self.assertEqual(self.model.buildsSize, "3 kB")
        self.assertEqual(self.model.artworkSize, "5 kB")
        self.assertEqual(self.model.buildsLast, "never")
        self.assertEqual(len(spy), 1)

        self.model.set_cache_meta(
            details="2 kB", builds="3 kB", artwork="5 kB", last_cached="never"
        )
        self.assertEqual(len(spy), 1)

    def test_button_state_is_per_kind(self):
        spy = Spy(self.model.buttonsChanged)

        self.model.set_button_state("builds", "Cancel", True, "Stop it")

        self.assertEqual(self.model.buildsButtonText, "Cancel")
        self.assertTrue(self.model.buildsButtonEnabled)
        self.assertEqual(self.model.buildsButtonTooltip, "Stop it")
        self.assertEqual(self.model.detailsButtonText, "Preload")
        self.assertEqual(len(spy), 1)

        self.model.set_button_state("builds", "Cancel", True, "Stop it")
        self.assertEqual(len(spy), 1)

    def test_status_and_clear_button(self):
        status = Spy(self.model.statusChanged)
        clear = Spy(self.model.clearButtonChanged)

        self.model.set_status("Preparing...")
        self.model.set_clear_button(False, "Cleared", "Wait")

        self.assertEqual(self.model.cacheStatus, "Preparing...")
        self.assertFalse(self.model.clearCacheEnabled)
        self.assertEqual(self.model.clearCacheText, "Cleared")
        self.assertEqual(self.model.clearCacheTooltip, "Wait")
        self.assertEqual(len(status), 1)
        self.assertEqual(len(clear), 1)

    def test_game_toggle_updates_the_rows_and_reports_the_action(self):
        self.model.games.reset_rows(GAMES)
        spy = Spy(self.model.gameToggled)

        self.model.setGameEnabled("hsr", False)

        self.assertFalse(self.model.games.is_enabled("hsr"))
        self.assertEqual(spy.calls, [("hsr", False)])

        self.model.setGameEnabled("hsr", False)
        self.assertEqual(len(spy), 1)

    def test_move_game_reorders_the_list_and_reports_the_action(self):
        self.model.order.reset_games(["zzz", "hsr", "gi"])
        spy = Spy(self.model.orderMoved)

        self.model.moveGame(0, 2)

        self.assertEqual(self.model.order.games(), ["hsr", "gi", "zzz"])
        self.assertEqual(spy.calls, [(0, 2)])

    def test_move_game_ignores_invalid_moves(self):
        self.model.order.reset_games(["zzz", "hsr"])
        spy = Spy(self.model.orderMoved)

        self.model.moveGame(0, 0)
        self.model.moveGame(5, 0)

        self.assertEqual(spy.calls, [])
        self.assertEqual(self.model.order.games(), ["zzz", "hsr"])

    def test_action_slots_relay_signals(self):
        preload = Spy(self.model.preloadRequested)
        clear = Spy(self.model.clearCacheRequested)
        reset = Spy(self.model.resetRequested)
        close = Spy(self.model.closeRequested)

        self.model.preload("details")
        self.model.clearCache()
        self.model.resetSection("order")
        self.model.requestClose()

        self.assertEqual(preload.calls, [("details",)])
        self.assertEqual(len(clear), 1)
        self.assertEqual(reset.calls, [("order",)])
        self.assertEqual(len(close), 1)

    def test_models_are_exposed_as_constants(self):
        self.assertIsInstance(self.model.games, GameToggleModel)
        self.assertIsInstance(self.model.order, GameOrderModel)


if __name__ == "__main__":
    unittest.main()
