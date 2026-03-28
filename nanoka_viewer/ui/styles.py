"""UI styles and theming."""

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
