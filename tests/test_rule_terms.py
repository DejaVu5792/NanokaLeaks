"""Game rule-term links and their details card.

Each game marks cross-references differently, but they all become anchors in
the rich-text descriptions and a shared Rule Terms card.  Genshin uses
``{LINK#N...}`` wrappers, Wuthering Waves ``<te href=...>`` tags, ZZZ
``<Term:...>`` tags, and Neverness to Everness ``<hot param="nouns&...">``.
"""

from __future__ import annotations

import unittest

from nanoka_viewer.api.detail_games import gi, nte, ww, zzz
from nanoka_viewer.api.detail_normalize import normalize
from nanoka_viewer.api.detail_text import format_markup

HYPERLINKS = {
    "11360001": {
        "name": "Gradient Beacons",
        "desc": "A <color=#FFD780FF>Gradient Beacon</color> lasts for Xs.\\n"
        "See also {LINK#N11360002}Detection Core{/LINK}.",
    },
    "11360002": {
        "name": "Detection Core",
        "desc": "An energy device.",
    },
}

WW_HYPERLINKS = {
    "850067": {
        "name": "Rabelle's Curve",
        "desc": "A test developed by Dr. Scott Rabelle. {0}",
        "param": ["It is safe."],
    },
    "151203": {
        "name": "Cradle Lullaby",
        "desc": "Lily's shield.",
    },
}

ZZZ_NOUNS = {
    "1000008": {
        "name": "Windbloom",
        "title": "Windbloom",
        "desc": "Gained when Velina enters the battlefield.",
    },
    "1000009": {
        "name": "Top Hat Companion",
        "title": "Top Hat Companion",
        "desc": "A companion in a top hat.",
    },
}

NTE_NOUNS = {
    "shinku_rage_e_energy": {
        "id": "ShinkuRageEEnergy",
        "title": "Fading Reason",
        "desc": "Energy required to cast Scarlet Descent.",
    },
    "shinku_rage": {
        "id": "ShinkuRage",
        "title": "Surging Crimson",
        "desc": "Consumes all Defiant Spirit.",
    },
}


class LinkMarkupTests(unittest.TestCase):
    def test_gi_rule_term_markup_becomes_an_anchor(self):
        markup = (
            '<color=#FFD780FF>{LINK#N11360001}Gradient Beacon{/LINK}</color>'
            " and {LINK#S11361}Chain Reaction{/LINK}"
        )

        rendered = format_markup(markup, term_names={"11360001": "Gradient Beacons"})

        self.assertIn('href="term:11360001"', rendered)
        self.assertIn("Gradient Beacon", rendered)
        self.assertNotIn("LINK#", rendered)
        self.assertNotIn("{/LINK}", rendered)
        # Skill links lose their wrapper and are not term anchors.
        self.assertIn("Chain Reaction", rendered)
        self.assertNotIn("term:S11361", rendered)

    def test_unknown_rule_terms_keep_their_text_but_lose_the_anchor(self):
        rendered = format_markup(
            "{LINK#N99999999}Missing{/LINK}", term_names={"1": "Known"}
        )

        self.assertIn("Missing", rendered)
        self.assertNotIn("href=", rendered)

    def test_ww_te_markup_becomes_an_anchor(self):
        rendered = format_markup(
            "<color=Highlight><te href=151203>Cradle Lullaby</te></color>",
            term_names={"151203": "Cradle Lullaby"},
        )

        self.assertIn('href="term:151203"', rendered)
        self.assertIn("Cradle Lullaby", rendered)
        self.assertNotIn("<te", rendered)

    def test_zzz_term_markup_and_bare_terms_use_the_noun_table(self):
        rendered = format_markup(
            "<Term:1000008>Windbloom</Term> and <Term:1000009>",
            term_names={
                "1000008": "Windbloom",
                "1000009": "Top Hat Companion",
            },
        )

        self.assertIn('href="term:1000008"', rendered)
        self.assertIn("Windbloom", rendered)
        self.assertIn('href="term:1000009"', rendered)
        self.assertIn("Top Hat Companion", rendered)
        self.assertNotIn("<Term:", rendered)

    def test_nte_hot_markup_becomes_an_anchor(self):
        rendered = format_markup(
            '<hot textstyle="TextEXPL" param="nouns&ShinkuRage">'
            "Surging Crimson</>",
            term_names={"ShinkuRage": "Surging Crimson"},
        )

        self.assertIn('href="term:ShinkuRage"', rendered)
        self.assertIn("Surging Crimson", rendered)
        self.assertNotIn("<hot", rendered)


class LinkedTermTests(unittest.TestCase):
    def test_gi_ids_are_unique_and_keep_their_first_appearance(self):
        raw = {
            "skills": [
                {
                    "desc": "Creates {LINK#N11360002}Detection Core{/LINK}.",
                }
            ],
            "passives": [
                {"desc": "Creates a {LINK#N11360001}Gradient Beacon{/LINK}."}
            ],
            "constellations": [
                {"desc": "Uses {LINK#N11360002}Detection Core{/LINK} again."}
            ],
        }

        self.assertEqual(
            gi.linked_term_ids(raw), ["11360002", "11360001"]
        )

    def test_gi_terms_are_resolved_from_the_shared_hyperlink_table(self):
        raw = {
            "skills": [
                {
                    "desc": "Creates a {LINK#N11360001}Gradient Beacon{/LINK}."
                    " Also {LINK#N99999999}missing{/LINK}."
                }
            ]
        }

        terms = gi.linked_terms(raw, HYPERLINKS)

        self.assertEqual(
            [term.name for term in terms], ["Gradient Beacons", "Detection Core"]
        )
        self.assertEqual(terms[0].term_id, "11360001")
        self.assertIn("Gradient Beacon", terms[0].text)
        self.assertNotIn("LINK#", terms[0].text)
        self.assertIn('href="term:11360002"', terms[0].text)
        self.assertIn("Detection Core", terms[0].text)

    def test_ww_terms_and_placeholders(self):
        raw = {
            "desc": "<te href=850067>Rabelle's Curve</te>",
            "skill_trees": {
                "3": {"skill": {"desc": "<te href=151203>Cradle Lullaby</te>"}}
            },
        }

        self.assertEqual(ww.linked_term_ids(raw), ["850067", "151203"])
        terms = ww.linked_terms(raw, WW_HYPERLINKS)

        self.assertEqual(
            [term.name for term in terms], ["Rabelle's Curve", "Cradle Lullaby"]
        )
        self.assertIn("It is safe.", terms[0].text)
        self.assertNotIn("{0}", terms[0].text)

    def test_zzz_terms_come_from_noun_json(self):
        raw = {
            "skill": {
                "basic": {
                    "description": [
                        {"desc": "Gains <Term:1000008>Windbloom</Term>."}
                    ]
                }
            },
            "passive": {
                "level": {
                    "1": {
                        "name": ["Core Passive"],
                        "desc": ["Uses <Term:1000009>Top Hat Companion</Term>."],
                    }
                }
            },
        }

        self.assertEqual(zzz.linked_term_ids(raw), ["1000008", "1000009"])
        terms = zzz.linked_terms(raw, ZZZ_NOUNS)

        self.assertEqual(
            [term.name for term in terms], ["Windbloom", "Top Hat Companion"]
        )
        self.assertEqual([term.term_id for term in terms], ["1000008", "1000009"])

    def test_nte_terms_are_embedded_in_the_payload(self):
        raw = {
            "desc": "Uses <hot textstyle=\"TextEXPL\" "
            'param="nouns&ShinkuRage">Surging Crimson</>.',
            "abilities": [{"phases": [{"desc": "Costs <hot "
                          'param="nouns&ShinkuRageEEnergy">Fading Reason</>.'}]}],
            "nouns": NTE_NOUNS,
        }

        self.assertEqual(
            nte.linked_term_ids(raw), ["ShinkuRage", "ShinkuRageEEnergy"]
        )
        terms = nte.linked_terms(raw)

        self.assertEqual(
            [term.name for term in terms], ["Surging Crimson", "Fading Reason"]
        )
        self.assertEqual(
            [term.term_id for term in terms], ["ShinkuRage", "ShinkuRageEEnergy"]
        )


class NormalizedDetailTests(unittest.TestCase):
    def test_gi_detail_carries_the_terms(self):
        raw = {
            "name": "Mitya",
            "rarity": "QUALITY_ORANGE",
            "weapon": "WEAPON_CATALYST",
            "element": "Electro",
            "skills": [
                {"desc": "Creates a {LINK#N11360001}Gradient Beacon{/LINK}."}
            ],
        }

        detail = normalize("gi", "1", raw, {"terms": HYPERLINKS})

        self.assertEqual(
            [term.name for term in detail.terms],
            ["Gradient Beacons", "Detection Core"],
        )
        self.assertIn('href="term:11360001"', detail.skills[0].description)

    def test_ww_detail_carries_the_terms(self):
        raw = {
            "name": "Lily",
            "rarity": 5,
            "element": "spectro",
            "weapon": "rectifier",
            "desc": "<te href=850067>Rabelle's Curve</te>",
            "chains": {
                "1": {
                    "name": "Sequence",
                    "desc": "<te href=151203>Cradle Lullaby</te>",
                }
            },
        }

        detail = normalize("ww", "1", raw, {"terms": WW_HYPERLINKS})

        self.assertEqual(
            [term.term_id for term in detail.terms], ["850067", "151203"]
        )
        self.assertIn('href="term:850067"', detail.overview)
        self.assertIn(
            'href="term:151203"', detail.extras[0].entries[0].text
        )

    def test_zzz_detail_carries_the_terms(self):
        raw = {
            "name": "Velina",
            "rarity": 4,
            "element_type": {"1": "Ether"},
            "weapon_type": {"1": "Attack"},
            "camp": {"1": "Spook Shack"},
            "skill": {
                "basic": {
                    "description": [
                        {"name": "Basic", "desc": "Gains <Term:1000008>Windbloom</Term>."}
                    ]
                }
            },
        }

        detail = normalize("zzz", "1", raw, {"terms": ZZZ_NOUNS})

        self.assertEqual([term.term_id for term in detail.terms], ["1000008"])
        self.assertIn('href="term:1000008"', detail.skills[0].description)

    def test_nte_detail_carries_embedded_terms(self):
        raw = {
            "name": "Exe",
            "rarity": 5,
            "desc": "Uses <hot textstyle=\"TextEXPL\" "
            'param="nouns&ShinkuRage">Surging Crimson</>.',
            "abilities": [],
            "nouns": NTE_NOUNS,
        }

        detail = normalize("nte", "1", raw, {})

        self.assertEqual([term.term_id for term in detail.terms], ["ShinkuRage"])
        self.assertIn('href="term:ShinkuRage"', detail.overview)


if __name__ == "__main__":
    unittest.main()
