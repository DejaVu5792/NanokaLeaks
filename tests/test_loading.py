"""Regression tests for progressive card loading and reload races."""

from __future__ import annotations

import unittest

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QPixmap

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

        def fake_request_image(url, callback, size=(100, 100), on_failed=None):
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


class PlaceholderGeometryTests(QtTestCase):
    """Loading placeholders must occupy exactly the real content's footprint."""

    def test_portrait_skeleton_matches_the_loaded_image_size(self):
        card = CardWidget("hsr", "1001", _HSR_CHAR)
        self.addCleanup(card.deleteLater)
        label = card.char_img_label

        self.assertEqual(label.size(), QSize(80, 80))
        self.assertFalse(label.has_image)
        self.assertLess(label.pulseAlpha, 255, "the portrait skeleton should pulse")

        before = [
            card.layout().itemAt(index).geometry()
            for index in range(card.layout().count())
        ]
        pixmap = QPixmap(80, 80)
        pixmap.fill(QColor("#ff0000"))
        card._on_char_image_loaded(pixmap)
        after = [
            card.layout().itemAt(index).geometry()
            for index in range(card.layout().count())
        ]

        self.assertTrue(label.has_image)
        self.assertEqual(label.size(), QSize(80, 80))
        self.assertEqual(
            label.pulseAlpha, 255, "the skeleton pulse must stop on success"
        )
        self.assertEqual(
            before, after, "loading the image must not move the card contents"
        )

    def test_failed_portrait_stops_loading(self):
        card = CardWidget("hsr", "1001", _HSR_CHAR)
        self.addCleanup(card.deleteLater)

        card._on_char_image_failed()

        self.assertFalse(card.char_img_label.has_image)
        self.assertEqual(
            card.char_img_label.pulseAlpha,
            255,
            "a failed image must not keep pulsing",
        )

    def test_pending_images_do_not_change_card_positions(self):
        section = GameSection("Test")
        section.resize(800, 240)
        section.show()
        self.addCleanup(section.deleteLater)

        for index in range(6):
            section.add_card("hsr", str(1000 + index), _HSR_CHAR)
        flush()

        positions = [card.pos() for card in section._cards]
        self.assertEqual(
            [second.x() - first.x() for first, second in zip(positions, positions[1:])],
            [188] * 5,
            "cards must sit on the normal 180px + 8px spacing grid",
        )
        self.assertEqual(
            len(section.cards_container.findChildren(CardWidget)),
            len(section._cards),
            "no extra loading widget may share the card row",
        )
        self.assertEqual(
            section.cards_container.width(),
            4 + 6 * 180 + 5 * 8 + 4,
            "the scrollable row must be exactly as wide as its card slots",
        )

        pixmap = QPixmap(80, 80)
        pixmap.fill(QColor("#ff0000"))
        for card in section._cards:
            card._on_char_image_loaded(pixmap)
        flush()

        self.assertEqual(
            [card.pos() for card in section._cards],
            positions,
            "loading the portraits must not move or resize the card row",
        )

    def test_card_grid_ignores_small_size_hints(self):
        """A card must keep its 180px slot even if its hint is stale/small.

        A QHBoxLayout can place fixed-size widgets using their *content* size
        hint (136px for a card whose icons/images are not loaded yet), which
        made the row overlap until a later relayout.  The grid is positioned
        explicitly, so hints can no longer affect it.
        """
        original_hint = CardWidget.sizeHint
        CardWidget.sizeHint = lambda self: QSize(136, 208)
        try:
            section = GameSection("Test")
            section.resize(800, 240)
            section.show()
            self.addCleanup(section.deleteLater)

            for index in range(4):
                section.add_card("hsr", str(1000 + index), _HSR_CHAR)
            flush()

            self.assertEqual(
                [card.x() for card in section._cards],
                [4, 192, 380, 568],
                "card positions must come from the grid, not from hints",
            )
            self.assertEqual(
                [card.width() for card in section._cards], [180] * 4
            )
        finally:
            CardWidget.sizeHint = original_hint


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
