"""QML tests for the per-game element/weapon filter bar."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtWidgets import QWidget

from support import QtTestCase, click_qml, find_qml_item, flush, wait

from nanoka_viewer.ui import filter_model, qml_host, view_model
from nanoka_viewer.ui.view_model import SectionsModel

_CHARS = {
    "1001": {"en": "Physical", "damageType": "Physical", "baseType": "Warrior"},
    "1002": {"en": "Fire", "damageType": "Fire", "baseType": "Rogue"},
    "1003": {"en": "Ice", "damageType": "Ice", "baseType": "Mage"},
}


class _StubViewer(QObject):
    changed = Signal()
    statusText = Property(str, lambda self: "Ready", notify=changed)
    cacheText = Property(str, lambda self: "", notify=changed)
    reloadText = Property(str, lambda self: "Reload", notify=changed)
    reloadEnabled = Property(bool, lambda self: True, notify=changed)

    @Slot()
    def reload(self):
        pass

    @Slot()
    def openSettings(self):
        pass

    @Slot(str, str)
    def openDetails(self, game, char_id):
        pass

    @Slot(str)
    def openExternal(self, url):
        pass


class FilterBarQmlTests(QtTestCase):
    def setUp(self):
        super().setUp()
        self.viewer = _StubViewer()
        self.sections = SectionsModel()
        with (
            patch.object(filter_model, "get_element_image", return_value=""),
            patch.object(filter_model, "get_specialty_image", return_value=""),
        ):
            self.sections.sync(["hsr"])
        self.section = self.sections.section("hsr")
        self.assertIsNotNone(self.section)
        with (
            patch.object(view_model, "get_character_image", return_value=""),
            patch.object(view_model, "get_element_image", return_value=""),
            patch.object(view_model, "get_specialty_image", return_value=""),
        ):
            self.section.characters.append_many(
                (char_id, data, False) for char_id, data in _CHARS.items()
            )

        self.host = QWidget()
        self.addCleanup(self.host.deleteLater)
        widget = qml_host.create_qml_widget(
            self.host,
            context_properties={
                "viewer": self.viewer,
                "sections": self.sections,
            },
        )
        self.addCleanup(widget.deleteLater)
        self.addCleanup(widget.setSource, QUrl())
        widget.setGeometry(0, 0, 640, 480)
        self.host.show()
        wait(100)
        flush()
        self.widget = widget
        self.root = widget.rootObject()
        self.assertIsNotNone(self.root)

    def _qml(self, name):
        item = find_qml_item(self.root, name)
        self.assertIsNotNone(item, f"{name} was not created")
        return item

    def _card_count(self):
        return self._qml("cardList").property("count")

    def test_bar_is_visible_by_default_and_filters_the_card_strip(self):
        self.assertTrue(self._qml("gameFilterBar").property("visible"))
        self.assertEqual(self._card_count(), 3)

        click_qml(self.widget, self._qml("filterCategory-Fire"))

        # The first click while everything is selected isolates the category.
        self.assertEqual(self._card_count(), 1)
        self.assertIn("Fire", self.section.filters.keys())
        self.assertEqual(self.section.filters.enabled_keys(), {"Fire"})

    def test_select_all_partial_selection_enables_then_disables(self):
        click_qml(self.widget, self._qml("filterCategory-Fire"))
        self.assertEqual(self._card_count(), 1)

        click_qml(self.widget, self._qml("filterSelectAll"))
        self.assertEqual(self._card_count(), 3)

        click_qml(self.widget, self._qml("filterSelectAll"))
        self.assertEqual(self._card_count(), 0)

    def test_mode_switch_shows_weapon_categories(self):
        click_qml(self.widget, self._qml("filterModeweapon"))
        self.assertEqual(self.section.filters.mode, "weapon")
        flush()
        wait(40)

        weapon = self._qml("filterCategory-The Hunt")
        click_qml(self.widget, weapon)

        self.assertEqual(self._card_count(), 1)

    def test_hiding_the_bar_shows_every_card(self):
        click_qml(self.widget, self._qml("filterCategory-Fire"))
        self.assertEqual(self._card_count(), 1)

        self.section.set_filters_enabled(False)
        flush()
        wait(40)

        self.assertFalse(self._qml("gameFilterBar").property("visible"))
        self.assertEqual(self._card_count(), 3)


if __name__ == "__main__":
    unittest.main()
