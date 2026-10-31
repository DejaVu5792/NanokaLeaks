"""Rendering regression tests.

These cover the two rendering bugs that were fixed outside of the View-button
work:

* QSS palette tokens must be kebab-case. Qt silently drops camelCase tokens
  such as ``palette(alternateBase)`` / ``palette(placeholderText)``, which made
  the details header and art column render without a background.
* The details surfaces must actually resolve their palette roles when the
  popup is shown (checked with pixel probes, not just by reading the QSS).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget

from support import (
    DETAILS_ROOT,
    QtTestCase,
    apply_catppuccin_palette,
    flush,
    make_details_host,
    open_details_for,
    wait,
    wait_for,
)

from nanoka_viewer.ui.styles import STYLESHEET

# A palette where every role has a distinct colour, so a dropped declaration
# cannot accidentally look correct (in Catppuccin, Window == AlternateBase).
DISTINCT_ROLES = {
    "Window": "#101010",
    "WindowText": "#e0e0e0",
    "Base": "#202020",
    "AlternateBase": "#303030",
    "ToolTipBase": "#404040",
    "ToolTipText": "#e0e0e0",
    "Text": "#e0e0e0",
    "Button": "#505050",
    "ButtonText": "#e0e0e0",
    "Mid": "#606060",
    "Midlight": "#707070",
    "Light": "#808080",
    "Dark": "#909090",
    "Shadow": "#000000",
    "Highlight": "#a0a0a0",
    "HighlightedText": "#000000",
    "PlaceholderText": "#b0b0b0",
}

# Qt's QSS palette(...) parser only understands these kebab-case spellings.
VALID_PALETTE_ROLES = {
    "window",
    "window-text",
    "base",
    "alternate-base",
    "tooltip-base",
    "tooltip-text",
    "placeholder-text",
    "text",
    "button",
    "button-text",
    "bright-text",
    "light",
    "midlight",
    "dark",
    "mid",
    "shadow",
    "highlight",
    "highlighted-text",
    "link",
    "link-visited",
    "accent",
}

PALETTE_TOKEN = re.compile(r"palette\(([A-Za-z][A-Za-z0-9-]*)\)")


class PaletteTokenTests(QtTestCase):
    def test_palette_tokens_are_valid_kebab_case(self):
        """No camelCase palette roles: Qt drops them without a warning."""
        offenders = []
        for path in sorted((Path(DETAILS_ROOT) / "nanoka_viewer").rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for match in PALETTE_TOKEN.finditer(text):
                token = match.group(1)
                if token not in VALID_PALETTE_ROLES:
                    offenders.append(
                        f"{path.relative_to(DETAILS_ROOT)}: palette({token})"
                    )
        self.assertEqual(
            offenders,
            [],
            "Invalid QSS palette tokens (use kebab-case, e.g. "
            "'alternate-base'):\n" + "\n".join(offenders),
        )

    def test_camel_case_palette_token_is_silently_dropped(self):
        """Documents the failure mode the camelCase regression fix addressed."""
        # Make Window and AlternateBase clearly different: in the Catppuccin
        # palette they are both #181825, which would hide the bug.
        palette = QPalette(self.application.palette())
        palette.setColor(QPalette.ColorRole.Window, QColor("#123456"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#abcdef"))
        self.application.setPalette(palette)

        host = QWidget()
        host.setStyleSheet(
            """
            QWidget#host { background: #123456; }
            QFrame#kebab  { background: palette(alternate-base); }
            QFrame#camel  { background: palette(alternateBase); }
            """
        )
        host.setObjectName("host")
        host.resize(240, 80)
        layout = QVBoxLayout(host)
        kebab = QFrame()
        kebab.setObjectName("kebab")
        kebab.setFixedSize(100, 60)
        camel = QFrame()
        camel.setObjectName("camel")
        camel.setFixedSize(100, 60)
        layout.addWidget(kebab)
        layout.addWidget(camel)
        host.show()
        flush()

        alternate_base = self.application.palette().color(
            QPalette.ColorRole.AlternateBase
        )
        self.assertEqual(
            kebab.grab().toImage().pixelColor(50, 30).name(),
            alternate_base.name(),
            "kebab-case palette role must resolve",
        )
        self.assertNotEqual(
            camel.grab().toImage().pixelColor(50, 30).name(),
            alternate_base.name(),
            "camelCase palette role is dropped by Qt and must not resolve",
        )
        host.deleteLater()

    def test_every_used_palette_role_renders_its_palette_colour(self):
        """End-to-end check that each role we use is accepted by QSS."""
        palette = self.application.palette()
        for role_name, colour in DISTINCT_ROLES.items():
            palette.setColor(
                getattr(QPalette.ColorRole, role_name), QColor(colour)
            )
        self.application.setPalette(palette)

        roles = sorted(
            role for role in ("base", "alternate-base", "button", "mid",
                              "highlight", "placeholder-text")
        )
        host = QWidget()
        qss = "\n".join(
            f"QFrame#role{i} {{ background: palette({role}); }}"
            for i, role in enumerate(roles)
        )
        host.setStyleSheet(qss)
        host.resize(len(roles) * 60, 60)
        frames = []
        for index, role in enumerate(roles):
            frame = QFrame(host)
            frame.setObjectName(f"role{index}")
            frame.setGeometry(index * 60, 0, 50, 50)
            frame.show()
            frames.append((role, frame))
        host.show()
        flush()

        for index, (role, _frame) in enumerate(frames):
            expected = palette.color(
                getattr(QPalette.ColorRole, self._role_name(role))
            )
            actual = host.grab().toImage().pixelColor(index * 60 + 25, 25)
            self.assertEqual(
                actual.name(),
                expected.name(),
                f"palette({role}) did not render as {expected.name()}",
            )
        host.deleteLater()

    @staticmethod
    def _role_name(token: str) -> str:
        return "".join(part.capitalize() for part in token.split("-"))


class DetailsSurfaceTests(QtTestCase):
    """The details popup must paint its themed surfaces, not fall back to base."""

    def setUp(self):
        super().setUp()
        palette = QPalette()
        for role_name, colour in DISTINCT_ROLES.items():
            palette.setColor(
                getattr(QPalette.ColorRole, role_name), QColor(colour)
            )
        self.application.setPalette(palette)

    def test_header_body_and_art_column_use_theme_roles(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)
        wait_for(
            lambda: popup._model.state == "ready",
            timeout=4000,
            message="the details content never rendered",
        )
        # Let the QQuickWidget render the frame the grab will read: it keeps
        # showing its previous frame until the next render pass.
        wait(150)

        alternate = QColor(DISTINCT_ROLES["AlternateBase"])
        base = QColor(DISTINCT_ROLES["Base"])

        image = popup.grab().toImage()
        panel = popup.panel_rect()
        art_width = round(panel.width() * 0.25)

        header = image.pixelColor(
            panel.left() + panel.width() // 2, panel.top() + 20
        )
        self.assertEqual(
            header.name(),
            alternate.name(),
            "details header must use palette(alternate-base)",
        )

        # The gradient overlay darkens the bottom edge, so probe near the top
        # where the overlay is fully transparent.
        art = image.pixelColor(panel.left() + art_width - 12, panel.top() + 56)
        self.assertLessEqual(
            max(
                abs(actual - expected)
                for actual, expected in zip(
                    art.getRgb()[:3], alternate.getRgb()[:3]
                )
            ),
            2,
            f"art column must use palette(alternate-base), got {art.name()}",
        )

        body = image.pixelColor(
            panel.left() + panel.width() - 20,
            panel.top() + panel.height() - 20,
        )
        self.assertEqual(
            body.name(),
            base.name(),
            "details body must use palette(base)",
        )

    def test_panel_is_not_transparent(self):
        window, central, _scroll, button, _anchor = make_details_host()
        self.track_window(window)
        popup = open_details_for(window, button)
        wait_for(
            lambda: popup._model.state == "ready",
            timeout=4000,
            message="the details content never rendered",
        )
        wait(150)

        base = QColor(DISTINCT_ROLES["Base"])
        image = popup.grab().toImage()
        panel = popup.panel_rect()
        # The gap between the art column and the first card is plain panel
        # background; a transparent QML root would show the dimmed backdrop.
        centre = image.pixelColor(
            panel.left() + round(panel.width() * 0.25) + 4,
            panel.top() + 56,
        )
        self.assertEqual(
            centre.name(),
            base.name(),
            "details panel must paint an opaque palette(base) background",
        )


class HoverStyleTests(QtTestCase):
    """Hover states must not turn the controls into a near-black 'pressed' look."""

    def test_hover_rules_do_not_use_the_light_role(self):
        # In KDE dark palettes QPalette.Light is darker than Button (Catppuccin:
        # #191922 vs #313244), so palette(light) reads as ':pressed'.
        self.assertNotIn(
            "palette(light)",
            STYLESHEET,
            "palette(light) is darker than palette(button) on dark KDE "
            "palettes; use palette(mid) for hover instead",
        )

    def test_view_button_hover_keeps_the_highlight_colour(self):
        block = re.search(
            r"QPushButton#viewBtn:hover\s*\{([^}]*)\}", STYLESHEET
        )
        self.assertIsNotNone(block)
        self.assertIn("palette(highlight)", block.group(1))
        self.assertNotIn("palette(light)", block.group(1))

    def test_rendered_hover_is_lighter_than_the_dark_light_role(self):
        apply_catppuccin_palette(self.application)
        host = QWidget()
        host.setStyleSheet(STYLESHEET)
        host.resize(220, 80)
        layout = QVBoxLayout(host)
        button = QPushButton("Hover")
        layout.addWidget(button)
        host.show()
        host.activateWindow()
        host.raise_()
        flush()

        QTest.mouseMove(button, button.rect().center())
        flush()

        hovered = button.grab().toImage().pixelColor(6, 6)
        light = self.application.palette().color(QPalette.ColorRole.Light)
        mid = self.application.palette().color(QPalette.ColorRole.Mid)
        self.assertEqual(hovered.name(), mid.name())
        self.assertGreater(
            hovered.lightness(),
            light.lightness(),
            "hover must not use the near-black Light role",
        )
        host.deleteLater()


if __name__ == "__main__":
    unittest.main()
