"""Genshin rule-term links and their details card.

Character descriptions wrap cross-references in ``{LINK#...}{/LINK}`` markup.
The visible text must survive, N-links must populate the shared Rule Terms
card, and other link kinds (skills, passives, ...) must simply disappear.
"""

from __future__ import annotations

import unittest

from nanoka_viewer.api.detail_games import gi
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


class LinkMarkupTests(unittest.TestCase):
    def test_rule_term_markup_keeps_the_visible_text(self):
        markup = (
            '<color=#FFD780FF>{LINK#N11360001}Gradient Beacon{/LINK}</color>'
            " and {LINK#S11361}Chain Reaction{/LINK}"
        )

        rendered = format_markup(markup)

        self.assertNotIn("LINK#", rendered)
        self.assertNotIn("{/LINK}", rendered)
        self.assertIn("Gradient Beacon", rendered)
        self.assertIn("Chain Reaction", rendered)


class LinkedTermTests(unittest.TestCase):
    def test_ids_are_unique_and_keep_their_first_appearance(self):
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

    def test_terms_are_resolved_from_the_shared_hyperlink_table(self):
        raw = {
            "skills": [
                {
                    "desc": "Creates a {LINK#N11360001}Gradient Beacon{/LINK}."
                    " Also {LINK#N99999999}missing{/LINK}."
                }
            ]
        }

        terms = gi.linked_terms(raw, HYPERLINKS)

        self.assertEqual([term.name for term in terms], ["Gradient Beacons"])
        self.assertIn("Gradient Beacon", terms[0].text)
        self.assertNotIn("LINK#", terms[0].text)
        self.assertIn("Detection Core", terms[0].text)

    def test_normalized_detail_carries_the_terms(self):
        raw = {
            "name": "Mitya",
            "rarity": "QUALITY_ORANGE",
            "weapon": "WEAPON_CATALYST",
            "element": "Electro",
            "skills": [
                {"desc": "Creates a {LINK#N11360001}Gradient Beacon{/LINK}."}
            ],
        }

        detail = normalize("gi", "1", raw, {"hyperlinks": HYPERLINKS})

        self.assertEqual(
            [term.name for term in detail.terms], ["Gradient Beacons"]
        )


if __name__ == "__main__":
    unittest.main()
