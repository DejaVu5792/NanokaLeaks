"""Embedded in-window browser popup for viewing character pages."""

import webbrowser

from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtGui import QColor, QKeySequence, QPainter, QShortcut
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .icons import apply_icon_or_text


class _BrowserView(QWebEngineView):
    """Web view that keeps new-window requests in this same view."""

    def createWindow(self, _type):
        return self


class BrowserPopup(QWidget):
    """Lightbox-style popup that renders a web page inside the main window."""

    def __init__(self, host):
        """Initialize the browser popup inside *host*."""
        super().__init__(host)
        self._host = host
        self.setObjectName("browserOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(
            """
            QWidget#browserOverlay {
                background-color: transparent;
            }
            QFrame#browserPanel {
                background: palette(base);
                border: 1px solid palette(mid);
                border-radius: 8px;
            }
            QFrame#browserHeader {
                background: palette(alternate-base);
                border: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QLabel#browserTitle {
                font-size: 12px;
                color: palette(text);
            }
            """
        )
        self.hide()

        self.panel = QFrame(self)
        self.panel.setObjectName("browserPanel")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("browserHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 6, 8, 6)
        header_layout.setSpacing(8)

        self.title_label = QLabel("Loading...")
        self.title_label.setObjectName("browserTitle")
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        header_layout.addWidget(self.title_label, 1)

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close_popup)

        self.open_external_btn = QPushButton()
        self.open_external_btn.setObjectName("iconBtn")
        self.open_external_btn.setFixedSize(26, 26)
        self.open_external_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_external_btn.setToolTip("Open in default browser")
        self.open_external_btn.setAccessibleName("Open in default browser")
        apply_icon_or_text(
            self.open_external_btn,
            ("external-link-symbolic", "external-link", "document-open-remote"),
            "\u2197",
        )
        self.open_external_btn.clicked.connect(self._open_external)

        header_layout.addWidget(self.open_external_btn)
        header_layout.addWidget(close_btn)

        panel_layout.addWidget(header)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.setStyleSheet(
            """
            QProgressBar {
                border: none;
                background: transparent;
            }
            QProgressBar::chunk {
                background: palette(highlight);
            }
            """
        )
        self.progress.hide()
        panel_layout.addWidget(self.progress)

        self.view = _BrowserView(self.panel)
        self.view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True
        )
        self.view.page().setBackgroundColor(self.palette().base().color())
        panel_layout.addWidget(self.view, 1)

        self._esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._esc_shortcut.activated.connect(self.close_popup)

        self.view.loadStarted.connect(self._on_load_started)
        self.view.loadProgress.connect(self._on_load_progress)
        self.view.loadFinished.connect(self._on_load_finished)
        self.view.titleChanged.connect(self._on_title_changed)

        self._host.installEventFilter(self)

    def open_url(self, url):
        """Show the popup and load *url*."""
        if not url:
            return
        self._update_geometry()
        self.show()
        self.raise_()
        self.panel.raise_()
        if self.windowHandle():
            self.windowHandle().raise_()
        self.progress.setValue(0)
        self.view.setUrl(QUrl(url))
        self.view.setFocus()

    def paintEvent(self, event):
        """Paint a dimmed overlay backdrop cleanly without Wayland QSS glitches."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 160))
        super().paintEvent(event)

    def _update_geometry(self):
        """Size the overlay to its host and center the popup panel."""
        rect = self._host.rect()
        self.setGeometry(rect)

        width = min(
            1100,
            max(420, int(rect.width() * 0.84)),
            max(200, rect.width() - 32),
        )
        height = min(
            800,
            max(300, int(rect.height() * 0.84)),
            max(150, rect.height() - 32),
        )
        self.panel.setGeometry(
            (rect.width() - width) // 2,
            (rect.height() - height) // 2,
            width,
            height,
        )
        self.raise_()
        self.panel.raise_()
        if self.windowHandle():
            self.windowHandle().raise_()
        self.update()
        self.panel.update()

    def close_popup(self):
        """Hide the popup and return focus to the main window."""
        self.view.stop()
        self.hide()
        self._host.setFocus()

    def _open_external(self):
        """Open the currently displayed page in the system browser."""
        url = self.view.url().toString()
        if url and url != "about:blank":
            webbrowser.open(url)

    def eventFilter(self, obj, event):
        """Keep the overlay sized to its host window."""
        if obj is self._host and event.type() in (QEvent.Type.Resize, QEvent.Type.WindowStateChange):
            self._update_geometry()
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        """Close the popup when the dimmed backdrop is clicked."""
        if not self.panel.geometry().contains(event.position().toPoint()):
            self.close_popup()
        super().mousePressEvent(event)

    def _on_load_started(self):
        self.progress.setValue(0)
        self.progress.show()
        self.title_label.setText("Loading...")

    def _on_load_progress(self, value):
        self.progress.setValue(value)

    def _on_load_finished(self, success):
        self.progress.hide()
        if not success:
            self.title_label.setText("Failed to load page")

    def _on_title_changed(self, title):
        text = title or "Nanoka Viewer"
        self.setWindowTitle(text)
        self.title_label.setText(text)
        self.title_label.setToolTip(text)


_popup = None


def open_browser(url, parent=None):
    """Show the shared in-window browser popup and load *url*."""
    global _popup
    if parent is None:
        return
    if isinstance(parent, QMainWindow):
        host = parent.centralWidget() or parent
    else:
        host = parent

    if _popup is None or _popup._host is not host:
        if _popup is not None:
            _popup.deleteLater()
        _popup = BrowserPopup(host)

    _popup.open_url(url)
