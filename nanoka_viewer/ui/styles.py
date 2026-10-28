"""UI styles and theming."""

STYLESHEET = """
QMainWindow, QWidget#centralWidget {
    background: palette(window);
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
    background: palette(mid);
}

QPushButton:pressed {
    background: palette(midlight);
}

QPushButton:disabled {
    background: palette(midlight);
    color: palette(placeholder-text);
    border: 1px solid palette(mid);
}

QPushButton#viewBtn {
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 11px;
    background: palette(highlight);
    color: palette(highlighted-text);
    border: 1px solid transparent;
}

QPushButton#viewBtn:hover {
    background: palette(highlight);
    color: palette(highlighted-text);
    border: 1px solid palette(window-text);
}

QPushButton#viewBtn:pressed {
    background: palette(mid);
    color: palette(button-text);
    border: 1px solid palette(mid);
}

QPushButton#iconBtn {
    padding: 0px;
    border-radius: 4px;
    background: palette(button);
    color: palette(button-text);
    border: 1px solid palette(mid);
}

QPushButton#iconBtn:hover {
    background: palette(mid);
}

QPushButton#iconBtn:pressed {
    background: palette(midlight);
}

QPushButton#viewBtn:disabled, QPushButton#iconBtn:disabled {
    background: palette(midlight);
    color: palette(placeholder-text);
    border: 1px solid palette(mid);
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
    background: palette(alternate-base);
}

QLabel#elementIcon, QLabel#specialtyIcon {
    border: 1px solid #444444;
    border-radius: 10px;
    background: #2A2A2A;
    color: palette(placeholder-text);
    font-size: 9px;
}

QWidget#detailsOverlay {
    background-color: transparent;
}

QFrame#detailsPanel {
    background: palette(base);
    border: 1px solid palette(mid);
    border-radius: 10px;
}

QFrame#settingsPanel {
    background: palette(base);
    border: 1px solid palette(mid);
    border-radius: 10px;
}

QFrame#settingsHeader {
    background: palette(alternate-base);
    border: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
}

QLabel#settingsTitle {
    font-size: 15px;
    font-weight: 700;
    color: palette(text);
}

QLabel#settingsSectionTitle {
    font-size: 12px;
    font-weight: 700;
    color: palette(text);
}

QLabel#settingsHint {
    color: palette(placeholder-text);
    font-size: 11px;
}

QPushButton#cacheBtn {
    padding: 4px 12px;
    font-size: 11px;
}

QTabWidget#settingsTabs::pane {
    border: 1px solid palette(mid);
    border-radius: 6px;
    top: -1px;
    background: palette(base);
}

QTabWidget#settingsTabs QTabBar::tab {
    background: transparent;
    color: palette(placeholder-text);
    border: none;
    border-bottom: 2px solid transparent;
    padding: 7px 16px;
    font-weight: 600;
}

QTabWidget#settingsTabs QTabBar::tab:hover {
    color: palette(text);
}

QTabWidget#settingsTabs QTabBar::tab:selected {
    color: palette(text);
    border-bottom: 2px solid palette(highlight);
}

QScrollArea#settingsScroll, QWidget#settingsPage {
    background: transparent;
    border: none;
}

QListWidget#gameOrderList {
    background: palette(base);
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 3px;
}

QListWidget#gameOrderList::item {
    padding: 7px 8px;
    border-radius: 4px;
    color: palette(text);
}

QListWidget#gameOrderList::item:hover {
    background: palette(alternate-base);
}

QListWidget#gameOrderList::item:selected {
    background: palette(highlight);
    color: palette(highlighted-text);
}

QListWidget#gameOrderList::item:drag {
    background: palette(mid);
}


QFrame#detailsHeader {
    background: palette(alternate-base);
    border: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
}

QWidget#detailsBody {
    background: palette(base);
}

QFrame#detailsArtColumn {
    background: palette(alternate-base);
    border: none;
    border-right: 1px solid palette(mid);
    border-bottom-left-radius: 10px;
}

QFrame#detailArtFrame {
    background: palette(alternate-base);
    border: none;
    border-bottom-left-radius: 10px;
}

QLabel#detailArt {
    color: palette(placeholder-text);
    background: transparent;
    border: none;
    font-size: 11px;
}

QLabel#detailArtPlaceholder {
    color: palette(placeholder-text);
    background: transparent;
    font-size: 11px;
}

QFrame#detailArtOverlay {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 rgba(0, 0, 0, 220),
        stop: 0.5 rgba(0, 0, 0, 120),
        stop: 1 rgba(0, 0, 0, 0)
    );
    border: none;
}

QLabel#detailArtName {
    color: #ffffff;
    background: transparent;
    font-size: 22px;
    font-weight: 700;
}

QLabel#detailArtMeta {
    color: rgba(255, 255, 255, 215);
    background: transparent;
    font-size: 11px;
}

QScrollArea#detailsScroll, QWidget#detailsContent {
    background: transparent;
    border: none;
}

QFrame#detailCard {
    background: palette(base);
    border: 1px solid palette(mid);
    border-radius: 8px;
}

QLabel#detailSectionTitle {
    font-size: 15px;
    font-weight: 700;
    color: palette(text);
}

QLabel#detailSubheading {
    font-size: 12px;
    font-weight: 700;
    color: palette(text);
}

QLabel#detailEntryName {
    font-size: 12px;
    font-weight: 700;
    color: palette(text);
}

QLabel#detailOverview {
    font-size: 12px;
    color: palette(text);
}

QLabel#detailMuted {
    color: palette(placeholder-text);
    font-size: 11px;
}

QLabel#detailLoadingLabel {
    color: palette(placeholder-text);
    font-size: 12px;
}

QFrame#detailSkeletonCard {
    background: palette(base);
    border: 1px solid palette(mid);
    border-radius: 8px;
}

QFrame#detailSkeletonBar {
    background: palette(midlight);
    border: none;
    border-radius: 4px;
}

QLabel#detailBuildItem {
    color: palette(text);
    font-size: 11px;
}

QLabel#detailStatValue {
    font-weight: 600;
    color: palette(text);
}

QLabel#detailMultiplier {
    font-weight: 600;
    color: palette(text);
}

QToolButton#detailDisclosure {
    text-align: left;
    padding: 7px 10px;
    border: 1px solid palette(mid);
    border-radius: 6px;
    background: palette(button);
    color: palette(button-text);
    font-weight: 600;
}

QToolButton#detailDisclosure:hover {
    background: palette(mid);
    color: palette(button-text);
}

QToolButton#detailDisclosure:checked {
    background: palette(alternate-base);
    color: palette(text);
}
"""
