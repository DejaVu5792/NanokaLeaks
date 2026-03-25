import webbrowser
import hashlib
import sys
import os
import time
import logging
from datetime import datetime
from pathlib import Path
from io import BytesIO

import requests
from PIL import Image
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QEvent
from PyQt6.QtGui import QPixmap, QImage

PALETTE_CHANGE_EVENT = QEvent.Type.PaletteChange

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

IMAGE_CACHE_DIR = Path.home() / ".cache" / "nanoka_leaks" / "images"
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

from nanoka_viewer.api import (
    get_newest_characters,
    get_character_url,
    get_rarity,
    get_element,
    get_name,
    get_character_image,
    get_element_image,
    get_specialty_image,
    GAMES,
)

IMAGE_CACHE = {}


def load_qt_image(url, size=(100, 100)):
    if not url:
        return None

    if url in IMAGE_CACHE:
        return IMAGE_CACHE[url]

    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_file = IMAGE_CACHE_DIR / f"{url_hash}.png"

    img = None
    if cache_file.exists():
        try:
            img = Image.open(cache_file).convert("RGBA")
        except Exception as e:
            logger.error(f"Failed to load cached image {cache_file}: {e}")

    if img is None:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content)).convert("RGBA")
                try:
                    img.save(cache_file, "PNG")
                except Exception as e:
                    logger.error(f"Failed to save image to cache: {e}")
        except Exception as e:
            logger.error(f"Failed to load image {url}: {e}")
            return None

    if img:
        img = img.resize(size, Image.Resampling.LANCZOS)
        data = img.tobytes("raw", "RGBA")
        qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimg)
        IMAGE_CACHE[url] = pixmap
        return pixmap
    return None


STYLESHEET = """
QMainWindow, QWidget#centralWidget {
    background: transparent;
}

QPushButton {
    padding: 6px 16px;
    border-radius: 6px;
    font-weight: 500;
    background: palette(button);
    color: palette(button-text);
    border: 1px solid palette(mid);
}

QPushButton:hover {
    background: palette(light);
}

QPushButton:pressed {
    background: palette(mid);
}

QPushButton#viewBtn {
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 11px;
    background: palette(highlight);
    color: palette(highlighted-text);
    border: none;
}

QPushButton#viewBtn:hover {
    background: palette(light);
    color: palette(button-text);
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    width: 6px;
    background: transparent;
}
QScrollBar::handle:vertical {
    background: palette(mid);
    border-radius: 3px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    height: 6px;
    background: transparent;
}
QScrollBar::handle:horizontal {
    background: palette(mid);
    border-radius: 3px;
    min-width: 30px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QWidget#card {
    border-radius: 10px;
    background: palette(base);
    border: 1px solid palette(mid);
}

QWidget#gameHeader {
    border-radius: 8px;
    background: palette(alternateBase);
}
"""


class LoadThread(QThread):
    game_loaded = pyqtSignal(str, list)
    load_finished = pyqtSignal()

    def run(self):
        total_start = time.time()
        for game in GAMES.keys():
            start = time.time()
            try:
                chars = get_newest_characters(game)
                elapsed = time.time() - start
                logger.info(
                    f"Loaded {len(chars)} characters for {game} in {elapsed:.3f}s"
                )
                self.game_loaded.emit(game, chars)
            except Exception as e:
                logger.error(f"Error loading {game}: {e}")
                self.game_loaded.emit(game, [])

        total_elapsed = time.time() - total_start
        logger.info(f"All data loaded in {total_elapsed:.3f}s")
        self.load_finished.emit()


class CardWidget(QWidget):
    def __init__(self, game, char_id, char_data, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedSize(180, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        name = get_name(game, char_data)
        rarity = get_rarity(game, char_data)
        element = get_element(game, char_data)
        url = get_character_url(game, char_id, char_data)

        char_img_url = get_character_image(game, char_data, char_id)
        element_img_url = get_element_image(game, char_data)
        specialty_img_url = get_specialty_image(game, char_data)

        rarity_colors = {"S": "#FF6B6B", "5": "#FFD700", "4": "#9370DB", "A": "#FF6B6B"}
        rarity_color = rarity_colors.get(str(rarity), "palette(text)")

        rarity_label = QLabel(f"{rarity}\u2605")
        rarity_label.setStyleSheet(
            f"color: {rarity_color}; font-weight: bold; font-size: 11px;"
        )
        rarity_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(rarity_label)

        char_img_label = QLabel()
        char_img_label.setFixedSize(80, 80)
        char_img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        char_pixmap = load_qt_image(char_img_url, (80, 80))
        if char_pixmap:
            char_img_label.setPixmap(char_pixmap)
        else:
            char_img_label.setText("No Image")
            char_img_label.setStyleSheet("color: palette(placeholderText);")
        layout.addWidget(char_img_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        icons_widget = QWidget()
        icons_layout = QHBoxLayout(icons_widget)
        icons_layout.setContentsMargins(0, 0, 0, 0)
        icons_layout.setSpacing(8)
        icons_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        element_label = QLabel()
        element_label.setFixedSize(18, 18)
        element_pixmap = load_qt_image(element_img_url, (18, 18))
        if element_pixmap:
            element_label.setPixmap(element_pixmap)
        else:
            element_label.setText(element[:3] if element else "?")
            element_label.setStyleSheet(
                "color: palette(placeholderText); font-size: 9px;"
            )
        icons_layout.addWidget(element_label)

        specialty_label = QLabel()
        specialty_label.setFixedSize(18, 18)
        specialty_pixmap = load_qt_image(specialty_img_url, (18, 18))
        if specialty_pixmap:
            specialty_label.setPixmap(specialty_pixmap)
        icons_layout.addWidget(specialty_label)

        layout.addWidget(icons_widget)

        display_name = name[:14] + ("..." if len(name) > 14 else "")
        name_label = QLabel(display_name)
        name_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(name_label)

        view_btn = QPushButton("View")
        view_btn.setObjectName("viewBtn")
        view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_btn.clicked.connect(lambda checked=False, u=url: webbrowser.open(u))
        layout.addWidget(view_btn)

        layout.addStretch()


class GameSection(QWidget):
    def __init__(self, game_name, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 8, 0, 8)
        main_layout.setSpacing(4)

        header = QWidget()
        header.setObjectName("gameHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)

        title_label = QLabel(game_name)
        title_label.setStyleSheet("font-weight: 600; font-size: 15px;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.status_label = QLabel("Loading...")
        self.status_label.setStyleSheet(
            "font-size: 12px; color: palette(placeholderText);"
        )
        header_layout.addWidget(self.status_label)

        main_layout.addWidget(header)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFixedHeight(230)

        self.cards_container = QWidget()
        self.cards_layout = QHBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(4, 0, 4, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        scroll_area.setWidget(self.cards_container)
        main_layout.addWidget(scroll_area)

    def clear_cards(self):
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def add_card(self, game, char_id, char_data):
        card = CardWidget(game, char_id, char_data)
        self.cards_layout.addWidget(card)

    def set_status(self, text):
        self.status_label.setText(text)


class NanokaViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("Initializing NanokaViewer...")
        init_start = time.time()

        self.setWindowTitle("Nanoka Viewer")
        self.setMinimumSize(800, 600)
        self.resize(950, 750)
        self._updating_theme = False
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(8)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Nanoka Viewer")
        title.setStyleSheet("font-weight: 600; font-size: 22px;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: palette(placeholderText);")
        header_layout.addWidget(self.status_label)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.load_data)
        header_layout.addWidget(self.refresh_btn)

        root_layout.addWidget(header_widget)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(self.content_widget)
        root_layout.addWidget(scroll_area)

        self.game_sections = {}
        games_list = list(GAMES.items())
        for i, (game, info) in enumerate(games_list):
            section = GameSection(info["name"])
            self.content_layout.addWidget(section)
            self.game_sections[game] = section

            if i < len(games_list) - 1:
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setFixedHeight(1)
                separator.setStyleSheet("background: palette(mid); border: none;")
                self.content_layout.addWidget(separator)

        self.load_thread = None

        init_elapsed = time.time() - init_start
        logger.info(f"GUI initialized in {init_elapsed:.3f}s")
        self.load_data()

    def load_data(self):
        logger.info("Starting data load...")
        self.refresh_btn.setEnabled(False)
        self.status_label.setText("Loading...")

        for section in self.game_sections.values():
            section.clear_cards()
            section.set_status("Loading...")

        self.load_thread = LoadThread()
        self.load_thread.game_loaded.connect(self.on_game_loaded)
        self.load_thread.load_finished.connect(self.on_load_finished)
        self.load_thread.start()

    def on_game_loaded(self, game, chars):
        section = self.game_sections.get(game)
        if not section:
            return

        section.clear_cards()

        if not chars:
            section.set_status("Failed to load characters")
            return

        section.set_status(f"{len(chars)} newest")

        card_start = time.time()
        for char_id, char_data in chars:
            section.add_card(game, char_id, char_data)
        card_elapsed = time.time() - card_start
        logger.info(f"Created {len(chars)} cards for {game} in {card_elapsed:.3f}s")

    def on_load_finished(self):
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"Loaded at {datetime.now().strftime('%H:%M:%S')}")
        logger.info("Load finished")

    def changeEvent(self, event):
        if event.type() == PALETTE_CHANGE_EVENT and not self._updating_theme:
            self._updating_theme = True
            self.setStyleSheet(STYLESHEET)
            self._updating_theme = False
        super().changeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = NanokaViewer()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
