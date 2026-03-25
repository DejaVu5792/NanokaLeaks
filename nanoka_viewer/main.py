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
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QImage, QFont, QColor, QPalette

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Image cache directory
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
    return None


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


class CardWidget(QFrame):
    def __init__(self, game, char_id, char_data, parent=None):
        super().__init__(parent)
        self.setFixedSize(180, 220)
        self.setStyleSheet(
            """
            CardWidget {
                background-color: #252525;
                border-radius: 8px;
            }
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        name = get_name(game, char_data)
        rarity = get_rarity(game, char_data)
        element = get_element(game, char_data)
        url = get_character_url(game, char_id, char_data)

        char_img_url = get_character_image(game, char_data, char_id)
        element_img_url = get_element_image(game, char_data)
        specialty_img_url = get_specialty_image(game, char_data)

        rarity_colors = {"S": "#FF6B6B", "5": "#FFD700", "4": "#9370DB", "A": "#FF6B6B"}
        rarity_color = rarity_colors.get(str(rarity), "#FFFFFF")

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        rarity_label = QLabel(f"{rarity}\u2605")
        rarity_label.setStyleSheet(
            f"color: {rarity_color}; font-weight: bold; font-size: 12px;"
        )
        rarity_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        top_row.addWidget(rarity_label, stretch=1)
        layout.addLayout(top_row)

        img_container = QWidget()
        img_layout = QVBoxLayout(img_container)
        img_layout.setContentsMargins(0, 0, 0, 0)
        img_layout.setSpacing(2)
        img_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        char_img_label = QLabel()
        char_img_label.setFixedSize(80, 80)
        char_img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        char_pixmap = load_qt_image(char_img_url, (80, 80))
        if char_pixmap:
            char_img_label.setPixmap(char_pixmap)
        else:
            char_img_label.setText("[No Img]")
            char_img_label.setStyleSheet("color: #666; font-size: 10px;")
        img_layout.addWidget(char_img_label, alignment=Qt.AlignmentFlag.AlignCenter)

        icons_layout = QHBoxLayout()
        icons_layout.setContentsMargins(0, 0, 0, 0)
        icons_layout.setSpacing(4)
        icons_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        element_label = QLabel()
        element_label.setFixedSize(18, 18)
        element_pixmap = load_qt_image(element_img_url, (18, 18))
        if element_pixmap:
            element_label.setPixmap(element_pixmap)
        else:
            element_label.setText(element[:3] if element else "N/A")
            element_label.setStyleSheet("color: #888; font-size: 9px;")
        icons_layout.addWidget(element_label)

        specialty_label = QLabel()
        specialty_label.setFixedSize(18, 18)
        specialty_pixmap = load_qt_image(specialty_img_url, (18, 18))
        if specialty_pixmap:
            specialty_label.setPixmap(specialty_pixmap)
        icons_layout.addWidget(specialty_label)

        img_layout.addLayout(icons_layout)
        layout.addWidget(img_container, alignment=Qt.AlignmentFlag.AlignCenter)

        display_name = name[:12] + ("..." if len(name) > 12 else "")
        name_label = QLabel(display_name)
        name_label.setStyleSheet("color: white; font-weight: bold; font-size: 11px;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        view_btn = QPushButton("View")
        view_btn.setFixedSize(60, 22)
        view_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #1f6aa5;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1a5a8a;
            }
        """
        )
        view_btn.clicked.connect(lambda: webbrowser.open(url))
        layout.addWidget(view_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()


class GameSection(QFrame):
    def __init__(self, game_name, parent=None):
        super().__init__(parent)
        self.game_name = game_name

        self.setStyleSheet("GameSection { background-color: #1a1a1a; }")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QFrame()
        header.setStyleSheet("background-color: #252525; border-radius: 4px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 8, 10, 8)

        title_label = QLabel(game_name)
        title_label.setStyleSheet("color: white; font-weight: bold; font-size: 16px;")
        header_layout.addWidget(title_label)

        self.status_label = QLabel("Loading...")
        self.status_label.setStyleSheet("color: #888; font-size: 12px;")
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        header_layout.addWidget(self.status_label)

        main_layout.addWidget(header)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFixedHeight(240)
        scroll_area.setStyleSheet(
            """
            QScrollArea {
                background-color: #1a1a1a;
                border: none;
            }
            QScrollBar:horizontal {
                background: #333333;
                height: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: #555555;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #666666;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
        """
        )

        self.cards_widget = QWidget()
        self.cards_widget.setStyleSheet("background-color: #1a1a1a;")
        self.cards_layout = QHBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(5, 5, 5, 5)
        self.cards_layout.setSpacing(8)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        scroll_area.setWidget(self.cards_widget)
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
        self.setGeometry(100, 100, 950, 750)
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #1a1a1a;
            }
        """
        )

        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #1a1a1a;")
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Nanoka Viewer")
        title.setStyleSheet("color: white; font-weight: bold; font-size: 20px;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888; font-size: 12px;")
        header_layout.addWidget(self.status_label)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setFixedSize(80, 30)
        self.refresh_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #1f6aa5;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1a5a8a;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """
        )
        self.refresh_btn.clicked.connect(self.load_data)
        header_layout.addWidget(self.refresh_btn)

        main_layout.addWidget(header)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            """
            QScrollArea {
                background-color: #1a1a1a;
                border: none;
            }
            QScrollBar:vertical {
                background: #333333;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #666666;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """
        )

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: #1a1a1a;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(scroll_area)

        self.game_sections = {}
        for game, info in GAMES.items():
            section = GameSection(info["name"])
            self.content_layout.addWidget(section)
            self.game_sections[game] = section

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


def main():
    app = QApplication(sys.argv)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1a1a1a"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("white"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#252525"))
    palette.setColor(QPalette.ColorRole.Text, QColor("white"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#1f6aa5"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("white"))
    app.setPalette(palette)

    window = NanokaViewer()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
