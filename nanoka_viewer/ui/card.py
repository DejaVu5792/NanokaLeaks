"""Character card widget for displaying character information."""

import logging
import subprocess
import sys
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..api import (
    get_character_image,
    get_character_url,
    get_element,
    get_element_image,
    get_name,
    get_rarity,
    get_specialty,
    get_specialty_image,
)
from .icons import apply_icon_or_text
from .image_loader import request_image

logger = logging.getLogger(__name__)


class CardWidget(QWidget):
    """Widget for displaying a single character card."""

    def __init__(self, game, char_id, char_data, is_new=False, parent=None):
        """Initialize the character card widget."""
        super().__init__(parent)
        self.game = game
        self.char_id = char_id
        self.char_data = char_data
        self.setObjectName("card")
        self.setFixedSize(180, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        name = get_name(game, char_data, char_id)
        rarity = get_rarity(game, char_data)
        element = get_element(game, char_data)
        url = get_character_url(game, char_id, char_data)

        self._char_img_url = get_character_image(game, char_data, char_id)
        self._element_img_url = get_element_image(game, char_data)
        self._specialty_img_url = get_specialty_image(game, char_data)
        self._images_requested = False
        self._image_requests = []

        rarity_colors = {"S": "#FF6B6B", "5": "#FFD700", "4": "#9370DB", "A": "#FF6B6B"}
        rarity_color = rarity_colors.get(str(rarity), "palette(text)")

        rarity_label = QLabel(f"{rarity}\u2605")
        rarity_label.setStyleSheet(
            f"color: {rarity_color}; font-weight: bold; font-size: 11px;"
        )
        rarity_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(rarity_label)

        self.char_img_label = QLabel()
        self.char_img_label.setFixedSize(80, 80)
        self.char_img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.char_img_label.setToolTip(name)
        self.char_img_label.setText("...")
        self.char_img_label.setStyleSheet("color: palette(placeholder-text);")
        layout.addWidget(self.char_img_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        icons_widget = QWidget()
        icons_layout = QHBoxLayout(icons_widget)
        icons_layout.setContentsMargins(0, 0, 0, 0)
        icons_layout.setSpacing(8)
        icons_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.element_label = QLabel()
        self.element_label.setObjectName("elementIcon")
        self.element_label.setFixedSize(20, 20)
        self.element_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.element_label.setToolTip(element if element else "Unknown Element")
        self.element_label.setText(element[:1] if element else "?")
        icons_layout.addWidget(self.element_label)

        specialty_type = get_specialty(game, char_data)
        self.specialty_label = QLabel()
        self.specialty_label.setObjectName("specialtyIcon")
        if self._specialty_img_url:
            self.specialty_label.setFixedSize(20, 20)
            self.specialty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.specialty_label.setToolTip(specialty_type)
            self.specialty_label.setText("?")
            icons_layout.addWidget(self.specialty_label)
        else:
            self.specialty_label.setVisible(False)

        layout.addWidget(icons_widget)

        display_name = name[:14] + ("..." if len(name) > 14 else "")
        name_label = QLabel(display_name)
        name_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(name_label)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(4)

        view_btn = QPushButton("View")
        view_btn.setObjectName("viewBtn")
        view_btn.setFixedHeight(28)
        view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_btn.setToolTip("Open character details")
        view_btn.clicked.connect(self._open_details)
        self.view_btn = view_btn
        actions.addWidget(view_btn, 1)

        browser_btn = QPushButton()
        browser_btn.setObjectName("iconBtn")
        browser_btn.setFixedSize(28, 28)
        browser_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browser_btn.setToolTip("Open in default browser")
        browser_btn.setAccessibleName("Open in default browser")
        apply_icon_or_text(
            browser_btn,
            ("external-link-symbolic", "external-link", "document-open-remote"),
            "\u2197",
        )
        browser_btn.clicked.connect(lambda checked=False, u=url: self._open_external_url(u))
        actions.addWidget(browser_btn)

        layout.addLayout(actions)

        layout.addStretch()

        # Add NEW badge overlay if character is new (top-left corner)
        if is_new:
            new_label = QLabel("NEW", self)
            new_label.setStyleSheet("""
                background-color: palette(highlight);
                color: palette(highlighted-text);
                border-radius: 3px;
                padding: 1px 3px;
                font-weight: bold;
                font-size: 8px;
            """)
            new_label.adjustSize()
            new_label.move(4, 4)
            new_label.raise_()

        # Images are *not* requested here.  GameSection calls
        # ensure_images_loaded() once the card is near the visible area, so a
        # cold start does not queue hundreds of off-screen downloads.

    def ensure_images_loaded(self):
        """Request this card's images once it is (nearly) on screen."""
        if self._images_requested:
            return
        self._images_requested = True
        self._request(self._char_img_url, self._on_char_image_loaded, (80, 80))
        self._request(self._element_img_url, self._on_element_image_loaded, (18, 18))
        if self._specialty_img_url:
            self._request(
                self._specialty_img_url, self._on_specialty_image_loaded, (18, 18)
            )

    def _request(self, url, callback, size):
        request = request_image(url, callback, size)
        if request is not None:
            self._image_requests.append(request)

    def cancel_image_requests(self):
        """Drop pending image callbacks (called before the card is deleted)."""
        for request in self._image_requests:
            request.cancel()
        self._image_requests.clear()

    def _open_details(self):
        """Open the native character details popup."""
        from .details import open_details

        button = getattr(self, "view_btn", None)
        logger.debug(
            "View clicked for %s/%s (underMouse=%s down=%s grabber=%r)",
            self.game,
            self.char_id,
            button.underMouse() if button is not None else None,
            button.isDown() if button is not None else None,
            QWidget.mouseGrabber(),
        )
        open_details(
            self.game,
            self.char_id,
            self.char_data,
            self.window(),
            source=button,
        )

    def _open_external_url(self, url):
        """Open a character page in the system default browser."""
        if not url:
            return
        if sys.platform.startswith("linux"):
            try:
                desktop = subprocess.check_output(
                    ["xdg-settings", "get", "default-web-browser"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
                if desktop:
                    subprocess.Popen(
                        ["gtk-launch", desktop, url],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    return
            except Exception:
                pass
        webbrowser.open(url, new=2)

    def _on_char_image_loaded(self, pixmap):
        """Update character image when loaded."""
        try:
            self.char_img_label.setText("")
            self.char_img_label.setPixmap(pixmap)
        except RuntimeError:
            pass  # The card was deleted while the image was in flight.

    def _on_element_image_loaded(self, pixmap):
        """Update element image when loaded."""
        try:
            self.element_label.setText("")
            self.element_label.setPixmap(pixmap)
        except RuntimeError:
            pass

    def _on_specialty_image_loaded(self, pixmap):
        """Update specialty image when loaded."""
        try:
            self.specialty_label.setText("")
            self.specialty_label.setPixmap(pixmap)
        except RuntimeError:
            pass
