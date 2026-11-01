"""Widget styles for the few controls the QML tree does not own.

The main view, the settings popup and the details popup are QML, so almost
every rule that used to live here is gone.  What remains is the widget chrome
Qt still paints around that tree:

* the window and central widget background;
* plain ``QPushButton``s, which the confirmation ``QMessageBox``es use (and the
  fake hosts in the tests);
* scroll bars for the widget-based test hosts;
* the transparent popup hosts, so the QML backdrop shows the window through.
"""

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

QWidget#detailsOverlay, QWidget#settingsOverlay {
    background-color: transparent;
}
"""
