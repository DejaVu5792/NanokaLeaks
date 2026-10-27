"""Regression tests for progressive card loading and reload races."""

from __future__ import annotations

import unittest

import support
from support import QtTestCase, flush, real_viewer

import nanoka_viewer.ui.card as card_module
from nanoka_viewer.ui.card import CardWidget
from nanoka_viewer.ui.section import GameSection

_HSR_CHAR = {
    "en": "Testchar",
    "rank": 5,
    "damageType": "Physical",
    "baseType": "Warrior",
    "icon": "TestIcon",
    "release": None,
}


class ImageVisibilityTests(QtTestCase):
    def setUp(self):
        super().setUp()
        self._original_request_image = card_module.request_image
        self.requests = []

        def fake_request_image(url, callback, size=(100, 100)):
            self.requests.append((url, size))
            return None

        card_module.request_image = fake_request_image

    def tearDown(self):
        card_module.request_image = self._original_request_image
        super().tearDown()

    def test_card_defers_image_requests_until_asked(self):
        card = CardWidget("hsr", "1001", _HSR_CHAR)
        self.addCleanup(card.deleteLater)

        self.assertEqual(self.requests, [])

        card.ensure_images_loaded()
        self.assertEqual(len(self.requests), 3)

        # Repeated visibility updates must not re-queue the same images.
        card.ensure_images_loaded()
        self.assertEqual(len(self.requests), 3)

        sizes = {size for _, size in self.requests}
        self.assertIn((80, 80), sizes)
        self.assertIn((18, 18), sizes)

    def test_section_only_requests_images_for_cards_near_viewport(self):
        section = GameSection("Test")
        section.resize(800, 240)
        section.show()
        self.addCleanup(section.deleteLater)

        for index in range(100):
            section.add_card("hsr", str(1000 + index), _HSR_CHAR)
        flush()

        requested_cards = [card for card in section._cards if card._images_requested]
        self.assertGreater(len(requested_cards), 0)
        self.assertLess(len(requested_cards), 100)
        self.assertEqual(len(self.requests), len(requested_cards) * 3)

        # Scrolling to the end loads the tail without re-requesting the head.
        scrollbar = section.scroll_area.horizontalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        flush()

        self.assertTrue(section._cards[-1]._images_requested)
        requested_after = [card for card in section._cards if card._images_requested]
        self.assertGreater(len(requested_after), len(requested_cards))
        self.assertEqual(len(self.requests), len(requested_after) * 3)


class ReloadRaceTests(QtTestCase):
    def _wait_for_idle(self, window, timeout=2000):
        elapsed = 0
        while not window.refresh_btn.isEnabled():
            support.wait(10)
            elapsed += 10
            if elapsed >= timeout:
                self.fail("window did not finish loading")

    def test_reload_is_ignored_while_a_load_is_active(self):
        with real_viewer() as (window, card):
            self.assertIsNotNone(card)
            self._wait_for_idle(window)

            window.load_data()
            first_thread = window.load_thread
            self.assertFalse(window.refresh_btn.isEnabled())
            self.assertEqual(window.refresh_btn.text(), "Loading...")

            window.load_data()
            self.assertIs(
                window.load_thread,
                first_thread,
                "a second Reload must not start another load",
            )

            self._wait_for_idle(window)
            self.assertEqual(window.refresh_btn.text(), "Reload")
            self.assertEqual(
                len(window.game_sections["hsr"]._cards),
                1,
                "spamming Reload must not duplicate cards",
            )

    def test_stale_generation_cannot_add_cards(self):
        with real_viewer() as (window, card):
            self.assertIsNotNone(card)
            self._wait_for_idle(window)
            window.load_data()
            stale_generation = window._load_generation - 1

            window.on_game_loaded(
                "hsr",
                [("9999", _HSR_CHAR, False)],
                stale_generation,
            )
            support.wait(30)

            char_ids = [c.char_id for c in window.game_sections["hsr"]._cards]
            self.assertNotIn("9999", char_ids)

    def test_reload_only_enables_refresh_after_cards_are_built(self):
        with real_viewer() as (window, card):
            self.assertIsNotNone(card)
            window.refresh_btn.setEnabled(False)
            window._pending_sections = {"hsr"}
            window._fetch_finished = True

            window._mark_section_done("other")
            self.assertFalse(window.refresh_btn.isEnabled())

            window._mark_section_done("hsr")
            self.assertTrue(window.refresh_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
