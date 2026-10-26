"""Regression tests for ZZZ recommended-build stat names."""

from __future__ import annotations

import unittest

from nanoka_viewer.api.details import _zzz_build


class ZzzBuildTests(unittest.TestCase):
    def test_phoenix_substats_are_named(self):
        raw = {
            "fairy_recommend": {
                "slot4": 31300,
                "slot2": 33000,
                "slot_sub": 31800,
                "part_sub_list": [31203, 12102],
                "part4": {"prop": 31402, "name": "Anomaly Mastery"},
                "part5": {"prop": 31203, "name": "Anomaly Proficiency"},
                "part6": {"prop": 31603, "name": "Fire DMG\xa0Bonus"},
            }
        }
        item_map = {
            "831320": {"name": "Freedom Blues"},
            "833020": {"name": "Phaethon's Melody"},
            "831820": {"name": "Chaos Jazz"},
        }
        sections = {section.title: section.items for section in _zzz_build(raw, {"item": item_map})}

        self.assertEqual(
            sections["Substats"],
            ["Anomaly Proficiency", "ATK%"],
        )
        self.assertIn("Drive Discs", sections)

    def test_robin_substats_are_named(self):
        raw = {
            "fairy_recommend": {
                "slot4": 33700,
                "slot2": 33100,
                "slot_sub": 31600,
                "part_sub_list": [11102, 11103],
                "part4": {"prop": 11102, "name": "HP"},
                "part5": {"prop": 30502, "name": "Energy Regen"},
                "part6": {"prop": 31903, "name": "Ether DMG Bonus"},
            }
        }
        item_map = {
            "833720": {"name": "Bunny in Wonderland"},
            "833120": {"name": "Yunkui Tales"},
            "831620": {"name": "Swing Jazz"},
        }
        sections = {section.title: section.items for section in _zzz_build(raw, {"item": item_map})}

        self.assertEqual(sections["Substats"], ["HP%", "HP"])

    def test_known_stat_mapping(self):
        props = [
            11102,
            11103,
            12102,
            12103,
            13102,
            13103,
            20103,
            21103,
            23103,
            23203,
            12202,
            30502,
            31203,
            31402,
        ]
        raw = {"fairy_recommend": {"part_sub_list": props}}
        sections = {section.title: section.items for section in _zzz_build(raw, {"item": {}})}

        self.assertEqual(
            sections["Substats"],
            [
                "HP%",
                "HP",
                "ATK%",
                "ATK",
                "DEF%",
                "DEF",
                "CRIT Rate",
                "CRIT DMG",
                "PEN Ratio",
                "PEN",
                "Impact",
                "Energy Regen",
                "Anomaly Proficiency",
                "Anomaly Mastery",
            ],
        )

    def test_unknown_stat_uses_part_name_fallback(self):
        raw = {
            "fairy_recommend": {
                "part_sub_list": [99999],
                "part_sub": {"prop": 99999, "name": "Custom\xa0Stat"},
            }
        }
        sections = {section.title: section.items for section in _zzz_build(raw, {"item": {}})}

        self.assertEqual(sections["Substats"], ["Custom Stat"])

    def test_unknown_stat_without_name_is_readable(self):
        raw = {"fairy_recommend": {"part_sub_list": [99999]}}
        sections = {section.title: section.items for section in _zzz_build(raw, {"item": {}})}

        self.assertEqual(sections["Substats"], ["Stat 99999"])

    def test_no_raw_numeric_substats_for_known_characters(self):
        props = [31203, 12102, 11102, 11103, 20103, 21103, 23103, 12202]
        raw = {"fairy_recommend": {"part_sub_list": props}}
        sections = {section.title: section.items for section in _zzz_build(raw, {"item": {}})}

        self.assertFalse(any(item.isdigit() for item in sections["Substats"]))


if __name__ == "__main__":
    unittest.main()