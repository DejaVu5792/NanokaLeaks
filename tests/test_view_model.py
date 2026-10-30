"""Unit tests for the QML view models.

The main view is rendered by QML, so the display rules that used to live in
the widget cards and sections now live in :mod:`nanoka_viewer.ui.view_model`.
These tests pin them down without needing a QML engine: every role the
delegates bind to, the batch-insertion contract the loader relies on, and the
set-vs-order semantics of ``SectionsModel.sync``.
"""

from __future__ import annotations

import unittest

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent

from support import QtTestCase

from nanoka_viewer.ui.view_model import (
    NAME_LIMIT,
    RARITY_COLORS,
    CharacterModel,
    Section,
    SectionsModel,
    display_name,
)

_HSR_CHAR = {
    "en": "Testchar",
    "rank": 5,
    "damageType": "Physical",
    "baseType": "Warrior",
    "icon": "TestIcon",
    "release": None,
}


class DisplayNameTests(unittest.TestCase):
    def test_short_names_are_untouched(self):
        self.assertEqual(display_name("Kafka"), "Kafka")

    def test_names_at_the_limit_are_untouched(self):
        name = "a" * NAME_LIMIT
        self.assertEqual(display_name(name), name)

    def test_long_names_are_truncated_with_an_ellipsis(self):
        name = "a" * (NAME_LIMIT + 1)
        self.assertEqual(display_name(name), "a" * NAME_LIMIT + "...")


class CharacterModelTests(QtTestCase):
    def _model(self):
        model = CharacterModel("hsr")
        self.addCleanup(model.deleteLater)
        return model

    def test_roles_cover_every_card_field(self):
        model = self._model()
        names = {bytes(value) for value in model.roleNames().values()}
        self.assertEqual(
            names,
            {
                b"charId",
                b"fullName",
                b"displayName",
                b"rarity",
                b"rarityColor",
                b"element",
                b"elementText",
                b"elementImage",
                b"specialty",
                b"specialtyImage",
                b"image",
                b"url",
                b"isNew",
            },
        )

    def test_append_many_precomputes_every_role(self):
        model = self._model()
        model.append_many([("1001", _HSR_CHAR, False)])

        self.assertEqual(model.rowCount(), 1)
        index = model.index(0, 0)
        self.assertEqual(model.data(index, CharacterModel.CharIdRole), "1001")
        self.assertEqual(model.data(index, CharacterModel.FullNameRole), "Testchar")
        self.assertEqual(model.data(index, CharacterModel.DisplayNameRole), "Testchar")
        self.assertEqual(model.data(index, CharacterModel.RarityRole), "5\u2605")
        self.assertEqual(
            model.data(index, CharacterModel.RarityColorRole),
            RARITY_COLORS["5"],
        )
        self.assertEqual(model.data(index, CharacterModel.ElementRole), "Physical")
        self.assertEqual(model.data(index, CharacterModel.ElementTextRole), "P")
        self.assertEqual(
            model.data(index, CharacterModel.ElementImageRole),
            "https://static.nanoka.cc/assets/hsr/element/physical.webp",
        )
        self.assertEqual(
            model.data(index, CharacterModel.SpecialtyRole), "Destruction"
        )
        self.assertEqual(
            model.data(index, CharacterModel.SpecialtyImageRole),
            "https://static.nanoka.cc/assets/hsr/pathicon/warrior.webp",
        )
        self.assertEqual(
            model.data(index, CharacterModel.ImageRole),
            "https://static.nanoka.cc/assets/hsr/avatarshopicon/1001.webp",
        )
        self.assertEqual(
            model.data(index, CharacterModel.UrlRole),
            "https://hsr.nanoka.cc/character/1001",
        )
        self.assertIs(model.data(index, CharacterModel.IsNewRole), False)

    def test_append_many_is_one_insertion(self):
        model = self._model()
        insertions = []
        model.rowsInserted.connect(
            lambda parent, first, last: insertions.append((first, last))
        )

        model.append_many(
            [("1001", _HSR_CHAR, False), ("1002", _HSR_CHAR, True)]
        )

        self.assertEqual(
            insertions,
            [(0, 1)],
            "a batch must produce a single rowsInserted, not one per card",
        )
        self.assertIs(model.data(model.index(1, 0), CharacterModel.IsNewRole), True)

    def test_append_many_ignores_empty_batches(self):
        model = self._model()
        resets = []
        model.modelReset.connect(lambda: resets.append(True))

        model.append_many([])

        self.assertEqual(model.rowCount(), 0)
        self.assertEqual(resets, [])

    def test_clear_resets_the_model_once(self):
        model = self._model()
        model.append_many([("1001", _HSR_CHAR, False)])
        resets = []
        model.modelReset.connect(lambda: resets.append(True))

        model.clear()

        self.assertEqual(model.rowCount(), 0)
        self.assertEqual(resets, [True])

        model.clear()
        self.assertEqual(resets, [True], "an empty clear must not reset again")

    def test_char_lookups(self):
        model = self._model()
        model.append_many([("1001", _HSR_CHAR, False), ("1002", _HSR_CHAR, True)])

        self.assertEqual(model.char_ids(), ["1001", "1002"])
        self.assertIs(model.char_data("1001"), _HSR_CHAR)
        self.assertIsNone(model.char_data("9999"))


class SectionTests(QtTestCase):
    def _section(self):
        section = Section("hsr", "Honkai: Star Rail")
        self.addCleanup(section.deleteLater)
        return section

    def test_initial_state(self):
        section = self._section()

        self.assertEqual(section.game, "hsr")
        self.assertEqual(section.name, "Honkai: Star Rail")
        self.assertEqual(section.status, "Loading...")
        self.assertEqual(section.liveVersion, "")
        self.assertEqual(section.latestVersion, "")
        self.assertIsInstance(section.characters, CharacterModel)

    def test_status_signal_only_fires_on_change(self):
        section = self._section()
        changes = []
        section.statusChanged.connect(lambda: changes.append(section.status))

        section.set_status("Loading 10/90")
        section.set_status("Loading 10/90")
        section.set_status("90 total")

        self.assertEqual(changes, ["Loading 10/90", "90 total"])

    def test_versions_signal_fires_once_for_a_pair(self):
        section = self._section()
        changes = []
        section.versionsChanged.connect(
            lambda: changes.append((section.liveVersion, section.latestVersion))
        )

        section.set_versions("1.2", "1.3+beta")
        section.set_versions("1.2", "1.3+beta")
        section.set_versions(None, None)

        self.assertEqual(
            changes,
            [("1.2", "1.3+beta"), ("", "")],
            "empty versions must be normalised to empty strings",
        )


class SectionsModelTests(QtTestCase):
    def _model(self):
        model = SectionsModel()
        self.addCleanup(model.deleteLater)
        return model

    def test_sync_creates_sections_in_order(self):
        model = self._model()

        changed = model.sync(["hsr", "gi"])

        self.assertTrue(changed)
        self.assertEqual(model.games(), ["hsr", "gi"])
        self.assertEqual(model.rowCount(), 2)
        first = model.data(model.index(0, 0), SectionsModel.SectionRole)
        self.assertIsInstance(first, Section)
        self.assertEqual(first.game, "hsr")
        self.assertEqual(first.name, "Honkai: Star Rail")

    def test_sync_ignores_unknown_games(self):
        model = self._model()

        model.sync(["hsr", "not-a-game"])

        self.assertEqual(model.games(), ["hsr"])

    def test_sync_is_a_no_op_when_nothing_changed(self):
        model = self._model()
        model.sync(["hsr", "gi"])
        section = model.section("hsr")
        resets = []
        model.modelReset.connect(lambda: resets.append(True))

        self.assertFalse(model.sync(["hsr", "gi"]))
        self.assertEqual(resets, [])
        self.assertIs(model.section("hsr"), section)

    def test_reorder_keeps_section_identity_and_reports_no_set_change(self):
        model = self._model()
        model.sync(["hsr", "gi"])
        hsr, gi = model.section("hsr"), model.section("gi")

        changed = model.sync(["gi", "hsr"])

        self.assertFalse(
            changed,
            "reordering must not look like a set change (it would reload)",
        )
        self.assertEqual(model.games(), ["gi", "hsr"])
        self.assertIs(model.section("hsr"), hsr)
        self.assertIs(model.section("gi"), gi)

    def test_removing_a_game_deletes_its_section(self):
        model = self._model()
        model.sync(["hsr", "gi"])
        removed = model.section("gi")

        self.assertTrue(model.sync(["hsr"]))
        self.assertIsNone(model.section("gi"))
        self.assertEqual(model.games(), ["hsr"])

        # deleteLater is deferred; flush it so the C++ object is really gone.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(shiboken6.isValid(removed))

    def test_adding_a_game_reports_a_set_change(self):
        model = self._model()
        model.sync(["hsr"])

        self.assertTrue(model.sync(["hsr", "gi"]))
        self.assertEqual(model.games(), ["hsr", "gi"])


if __name__ == "__main__":
    unittest.main()
