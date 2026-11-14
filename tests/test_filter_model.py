"""Tests for the per-game element/weapon filter model and proxy."""

from __future__ import annotations

import unittest

from PySide6.QtCore import QModelIndex

from support import QtTestCase

from nanoka_viewer.ui.filter_model import (
    MODE_ELEMENT,
    MODE_WEAPON,
    CharacterFilterProxy,
    FilterModel,
    build_filter_catalog,
    element_catalog,
    weapon_catalog,
)
from nanoka_viewer.ui.view_model import CharacterModel

_HSR_CHARS = {
    "1001": {"en": "Physical", "damageType": "Physical", "baseType": "Warrior"},
    "1002": {"en": "Fire", "damageType": "Fire", "baseType": "Rogue"},
    "1003": {"en": "Ice", "damageType": "Ice", "baseType": "Mage"},
}


def _keys(categories):
    return [item["key"] for item in categories]


class FilterCatalogTests(unittest.TestCase):
    def test_every_game_has_an_element_catalog(self):
        for game in ("zzz", "hsr", "gi", "ww", "nte"):
            categories = element_catalog(game)
            self.assertTrue(categories, game)
            for category in categories:
                self.assertTrue(category["icon"], (game, category))

    def test_nte_has_only_elements(self):
        self.assertTrue(element_catalog("nte"))
        self.assertEqual(weapon_catalog("nte"), [])
        catalog = build_filter_catalog("nte")
        self.assertTrue(catalog[MODE_ELEMENT])
        self.assertEqual(catalog[MODE_WEAPON], [])

    def test_weapon_catalogs_follow_the_card_artwork(self):
        self.assertEqual(
            _keys(weapon_catalog("hsr")),
            [
                "Destruction",
                "The Hunt",
                "Erudition",
                "Preservation",
                "Nihility",
                "Abundance",
                "Harmony",
                "Remembrance",
                "Elation",
            ],
        )
        self.assertEqual(
            _keys(weapon_catalog("gi")),
            ["Sword", "Claymore", "Polearm", "Bow", "Catalyst"],
        )
        self.assertIn("Broadblade", _keys(weapon_catalog("ww")))
        self.assertIn("Attack", _keys(weapon_catalog("zzz")))


class FilterModelTests(QtTestCase):
    def setUp(self):
        super().setUp()
        self.model = FilterModel("hsr")

    def test_defaults_to_elements_everything_enabled(self):
        self.assertEqual(self.model.mode, MODE_ELEMENT)
        self.assertTrue(self.model.weaponAvailable)
        self.assertTrue(self.model.allEnabled)
        self.assertEqual(
            self.model.enabled_keys(),
            set(self.model.keys()),
        )

    def test_row_roles(self):
        index = self.model.index(0, 0)
        self.assertEqual(self.model.data(index, self.model.KeyRole), "Physical")
        self.assertEqual(self.model.data(index, self.model.LabelRole), "Physical")
        self.assertTrue(self.model.data(index, self.model.EnabledRole))
        self.assertTrue(self.model.data(index, self.model.IconRole))
        self.assertIsNone(self.model.data(QModelIndex()))

    def test_toggle_only_affects_one_category(self):
        self.model.set_single_selection(False)
        self.model.toggle("Fire")
        self.model.toggle("Fire")
        self.model.toggle("Ice")

        self.assertFalse(self.model.data(self.model.index(1, 0), self.model.EnabledRole))
        self.assertTrue(self.model.data(self.model.index(2, 0), self.model.EnabledRole))
        self.assertFalse(self.model.allEnabled)

    def test_single_selection_defaults_on(self):
        self.assertTrue(self.model.singleSelection)

    def test_single_selection_replaces_the_previous_filter(self):
        self.model.toggle("Fire")
        self.model.toggle("Ice")

        self.assertEqual(self.model.enabled_keys(), {"Ice"})

    def test_clicking_the_active_single_filter_clears_it(self):
        self.model.toggle("Fire")
        self.model.toggle("Fire")

        self.assertTrue(self.model.allEnabled)
        self.assertEqual(self.model.enabled_keys(), set(self.model.keys()))

    def test_multi_selection_checkbox_allows_several_filters(self):
        self.model.set_single_selection(False)
        self.assertFalse(self.model.singleSelection)

        # As in multi-select, the first click over an unfiltered strip
        # isolates the category, and later clicks extend the selection.
        self.model.toggle("Fire")
        self.assertEqual(self.model.enabled_keys(), {"Fire"})

        self.model.toggle("Ice")
        self.assertEqual(self.model.enabled_keys(), {"Fire", "Ice"})

    def test_first_click_isolates_when_everything_is_enabled(self):
        changed = []
        self.model.stateChanged.connect(lambda: changed.append(True))

        self.model.toggle("Fire")

        self.assertEqual(self.model.enabled_keys(), {"Fire"})
        self.assertFalse(self.model.allEnabled)
        self.assertEqual(len(changed), 1)

    def test_select_all_partial_selection_enables_everything_first(self):
        self.model.toggle("Fire")

        self.model.toggleAll()
        self.assertTrue(self.model.allEnabled)
        self.assertEqual(self.model.enabled_keys(), set(self.model.keys()))

        self.model.toggleAll()
        self.assertFalse(self.model.allEnabled)
        self.assertEqual(self.model.enabled_keys(), set())

    def test_mode_switch_preserves_each_catalog_selection(self):
        self.model.toggle("Fire")
        self.model.setMode(MODE_WEAPON)

        self.assertEqual(self.model.mode, MODE_WEAPON)
        self.assertTrue(self.model.allEnabled)
        self.assertIn("Destruction", self.model.enabled_keys())

        self.model.toggle("The Hunt")
        self.assertEqual(self.model.enabled_keys(), {"The Hunt"})
        self.model.setMode(MODE_ELEMENT)

        self.assertEqual(self.model.enabled_keys(), {"Fire"})
        self.assertNotIn("Physical", self.model.enabled_keys())

    def test_mode_switch_stays_on_elements_without_a_weapon_catalog(self):
        model = FilterModel("nte")
        self.assertFalse(model.weaponAvailable)

        model.setMode(MODE_WEAPON)

        self.assertEqual(model.mode, MODE_ELEMENT)

    def test_add_categories_merges_new_and_ignores_placeholders(self):
        self.model.add_categories(
            MODE_ELEMENT,
            [
                {"key": "Physical", "icon": "known"},
                {"key": "Lumiflux", "icon": "new"},
                {"key": "Unknown", "icon": "ignored"},
                {"key": "", "icon": "ignored"},
                {"key": "NoIcon", "icon": ""},
            ],
        )

        self.assertIn("Lumiflux", self.model.keys())
        self.assertIn("Lumiflux", self.model.enabled_keys())
        self.assertNotIn("Unknown", self.model.keys())
        self.assertNotIn("NoIcon", self.model.keys())

        # Adding the same category again is a no-op.
        self.model.add_categories(
            MODE_ELEMENT, [{"key": "Lumiflux", "icon": "new"}]
        )
        self.assertEqual(self.model.keys().count("Lumiflux"), 1)

    def test_genshin_physical_fallback_is_not_a_filter(self):
        self.assertNotIn("Physical", _keys(element_catalog("gi")))

        model = FilterModel("gi")
        model.add_categories(
            MODE_ELEMENT, [{"key": "Physical", "icon": "fallback"}]
        )

        self.assertNotIn("Physical", model.keys())


class GenshinWeaponFilterTests(QtTestCase):
    """GI cards report raw weapon codes; the filters use display names."""

    def _filters_for(self, chars):
        source = CharacterModel("gi")
        self.addCleanup(source.deleteLater)
        source.append_many(
            (char_id, data, False) for char_id, data in chars.items()
        )
        filters = FilterModel("gi")
        self.addCleanup(filters.deleteLater)
        filters.add_categories(
            MODE_WEAPON,
            [
                {"key": specialty, "icon": icon}
                for _, _, specialty, icon in source.filter_values()
            ],
        )
        return source, filters

    def test_weapon_categories_merge_without_duplicates(self):
        _, filters = self._filters_for(
            {
                "10000002": {
                    "en": "Kamisato Ayaka",
                    "element": "Cryo",
                    "weapon": "WEAPON_SWORD_ONE_HAND",
                }
            }
        )

        self.assertEqual(
            filters.keys(MODE_WEAPON),
            ["Sword", "Claymore", "Polearm", "Bow", "Catalyst"],
        )

    def test_sword_filter_matches_the_sword_card(self):
        source, filters = self._filters_for(
            {
                "10000002": {
                    "en": "Kamisato Ayaka",
                    "element": "Cryo",
                    "weapon": "WEAPON_SWORD_ONE_HAND",
                }
            }
        )
        filters.setMode(MODE_WEAPON)
        filters.setAllEnabled(False)
        filters.toggle("Sword")
        proxy = CharacterFilterProxy(
            source,
            filters,
            element_role=CharacterModel.ElementRole,
            weapon_role=CharacterModel.SpecialtyRole,
        )
        self.addCleanup(proxy.deleteLater)

        ids = [
            proxy.data(proxy.index(row, 0), CharacterModel.CharIdRole)
            for row in range(proxy.rowCount())
        ]
        self.assertEqual(ids, ["10000002"])

    def test_traveler_crossbow_is_not_a_filter(self):
        _, filters = self._filters_for(
            {
                "10000134": {
                    "en": "Traveler",
                    "weapon": "WEAPON_CROSSBOW",
                }
            }
        )

        self.assertNotIn("Crossbow", filters.keys(MODE_WEAPON))


class CharacterFilterProxyTests(QtTestCase):
    def setUp(self):
        super().setUp()
        self.source = CharacterModel("hsr")
        self.source.append_many(
            (char_id, data, False) for char_id, data in _HSR_CHARS.items()
        )
        self.filters = FilterModel("hsr")
        self.filters.set_single_selection(False)
        self.proxy = CharacterFilterProxy(
            self.source,
            self.filters,
            element_role=CharacterModel.ElementRole,
            weapon_role=CharacterModel.SpecialtyRole,
        )

    def _ids(self):
        return [
            self.proxy.data(self.proxy.index(row, 0), CharacterModel.CharIdRole)
            for row in range(self.proxy.rowCount())
        ]

    def test_shows_every_card_by_default(self):
        self.assertEqual(self.proxy.rowCount(), 3)

    def test_disabled_element_hides_its_cards(self):
        self.filters.setAllEnabled(False)
        self.filters.toggle("Physical")
        self.filters.toggle("Ice")

        self.assertEqual(self._ids(), ["1001", "1003"])

    def test_disabled_weapon_hides_its_cards_in_weapon_mode(self):
        self.filters.setMode(MODE_WEAPON)
        self.filters.setAllEnabled(False)
        self.filters.toggle("Destruction")
        self.filters.toggle("Erudition")

        self.assertEqual(self._ids(), ["1001", "1003"])

    def test_turning_the_feature_off_shows_every_card(self):
        self.filters.setAllEnabled(False)
        self.assertEqual(self.proxy.rowCount(), 0)

        self.proxy.setFilteringEnabled(False)
        self.assertFalse(self.proxy.filteringEnabled())
        self.assertEqual(self.proxy.rowCount(), 3)

        self.proxy.setFilteringEnabled(True)
        self.assertEqual(self.proxy.rowCount(), 0)


if __name__ == "__main__":
    unittest.main()
