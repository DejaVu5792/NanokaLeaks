"""Native in-window character details view."""

from __future__ import annotations

import logging

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QCursor,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..api.details import (
    BuildSection,
    CharacterDetail,
    DetailUnavailable,
    ExtraSection,
    SkillDetail,
    load_character_art,
    load_character_build,
    load_character_detail,
)
from .overlay import OverlayPopup, is_alive

logger = logging.getLogger(__name__)


class _DetailLoadThread(QThread):
    """Fetch a character detail payload without blocking the UI."""

    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, game: str, char_id: str, parent=None):
        super().__init__(parent)
        self._game = game
        self._char_id = char_id

    def run(self):
        try:
            self.loaded.emit(load_character_detail(self._game, self._char_id))
        except DetailUnavailable as exc:
            self.failed.emit(str(exc))
        except Exception:
            logger.exception("Failed to load character details")
            self.failed.emit("Could not load character details. Please try again.")


class _BuildLoadThread(QThread):
    """Fetch recommended-build metadata separately from the text payload."""

    loaded = Signal(object)
    failed = Signal()

    def __init__(self, detail: CharacterDetail, parent=None):
        super().__init__(parent)
        self._detail = detail

    def run(self):
        try:
            self.loaded.emit(load_character_build(self._detail))
        except Exception:
            logger.exception("Failed to load recommended build")
            self.failed.emit()


class _ArtLoadThread(QThread):
    """Fetch character art separately from the text payload."""

    loaded = Signal(object)
    failed = Signal()

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        data = load_character_art(self._url)
        if data:
            self.loaded.emit(data)
        else:
            self.failed.emit()


class _ArtLabel(QLabel):
    """Artwork label that keeps the image fitted while its column resizes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(1, 1)

        # Resizing a window fires a burst of resize events; smooth-scaling a
        # large artwork for each one is wasted work. Coalesce them.
        self._rescale_timer = QTimer(self)
        self._rescale_timer.setSingleShot(True)
        self._rescale_timer.setInterval(40)
        self._rescale_timer.timeout.connect(self._rescale)

    def set_source(self, pixmap: QPixmap | None):
        """Set the source artwork and fit it to the current label size."""
        self._source = pixmap
        self._rescale_timer.stop()
        if pixmap is None or pixmap.isNull():
            self.clear()
        else:
            self._rescale()

    def clear_source(self):
        """Drop the cached source artwork so rescale doesn't resurrect it."""
        self._rescale_timer.stop()
        self._source = None
        self.clear()

    def _rescale(self):
        if self._source is None or self._source.isNull():
            return
        target = self.size()
        if target.width() <= 0 or target.height() <= 0:
            return
        scaled = self._source.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Centre horizontally, but keep the top: character faces live there.
        if scaled.width() > target.width() or scaled.height() > target.height():
            x = max(0, (scaled.width() - target.width()) // 2)
            scaled = scaled.copy(x, 0, target.width(), target.height())
        self.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale_timer.start()


class _CollapsibleSection(QWidget):
    """A disclosure section that is collapsed by default."""

    def __init__(self, title: str, body: QWidget, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.button = QToolButton()
        self.button.setObjectName("detailDisclosure")
        self.button.setText(title.replace("&", "&&"))
        self.button.setToolTip(title)
        self.button.setCheckable(True)
        self.button.setChecked(False)
        self.button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.button.setArrowType(Qt.ArrowType.RightArrow)
        self.button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self._on_toggled)
        layout.addWidget(self.button)

        self.body = body
        self.body.setVisible(False)
        layout.addWidget(self.body)

    def _on_toggled(self, checked: bool):
        self.body.setVisible(checked)
        self.button.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )


class CharacterDetailsPopup(OverlayPopup):
    """Lightbox-style character details overlay."""

    overlay_object_name = "detailsOverlay"
    panel_object_name = "detailsPanel"
    blocks_host_input = True
    log_name = "details popup"
    logger = logging.getLogger(__name__)

    def __init__(self, host):
        super().__init__(host)
        self._request_id = 0
        self._thread: _DetailLoadThread | None = None
        self._build_thread: _BuildLoadThread | None = None
        self._art_thread: _ArtLoadThread | None = None
        self._art_label: _ArtLabel | None = None
        self._build_skeleton: QWidget | None = None
        self._skeleton_animation: QPropertyAnimation | None = None
        self._game = ""
        self._char_id = ""
        self._source: QWidget | None = None

        panel_layout = self.panel_layout

        header = QFrame()
        header.setObjectName("detailsHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 12, 10)
        header_layout.setSpacing(10)

        header_layout.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._request_close)
        header_layout.addWidget(close_btn)

        panel_layout.addWidget(header)

        self.body = QWidget()
        self.body.setObjectName("detailsBody")
        body_layout = QHBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.art_column = QFrame()
        self.art_column.setObjectName("detailsArtColumn")
        self.art_column.setFixedWidth(240)
        self.art_column.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        self.art_layout = QVBoxLayout(self.art_column)
        self.art_layout.setContentsMargins(0, 0, 0, 0)
        self.art_layout.setSpacing(0)
        body_layout.addWidget(self.art_column, 0)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("detailsScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.content = QWidget()
        self.content.setObjectName("detailsContent")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(16, 16, 16, 16)
        self.content_layout.setSpacing(12)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.content)
        body_layout.addWidget(self.scroll, 1)

        panel_layout.addWidget(self.body, 1)

    def open_character(
        self, game: str, char_id: str, source: QWidget | None = None
    ):
        """Show the popup and fetch *char_id*'s details from nanoka.cc.

        *source* is the widget that triggered the popup (usually the card's
        View button).  Its hover/pressed state is cleared so it does not keep
        painting as if it were still interactive underneath the overlay.
        """
        self._game = game
        self._char_id = char_id
        self._source = source
        self._request_id += 1
        request_id = self._request_id

        cursor_pos = QCursor.pos()
        logger.debug(
            "open details %s/%s source=%r grabber=%r widget_at_cursor=%r "
            "focus=%r",
            game,
            char_id,
            source,
            QWidget.mouseGrabber(),
            QApplication.widgetAt(cursor_pos),
            QApplication.focusWidget(),
        )

        self.clear_stale_input_state(source)
        self._clear_content()
        self._show_loading()
        self.show_overlay()
        self.scroll.verticalScrollBar().setValue(0)
        logger.debug(
            "details shown: host=%s overlay=%s panel=%s visible=%s "
            "focus=%r guard=%s",
            self._host.size(),
            self.size(),
            self.panel.geometry(),
            self.isVisible(),
            QApplication.focusWidget(),
            self._input_guard_installed,
        )
        self._start_load(request_id)

    def _start_load(self, request_id: int):
        thread = _DetailLoadThread(self._game, self._char_id, self)
        thread.loaded.connect(
            lambda detail: self._on_loaded(request_id, detail)
        )
        thread.failed.connect(lambda message: self._on_failed(request_id, message))
        thread.finished.connect(lambda t=thread: self._on_thread_finished(t))
        self._thread = thread
        thread.start()

    def _on_thread_finished(self, thread: _DetailLoadThread):
        if self._thread is thread:
            self._thread = None
        thread.deleteLater()

    def _on_loaded(self, request_id: int, detail: CharacterDetail):
        if request_id != self._request_id or not self.isVisible():
            return
        self._clear_content()
        self._build_content(detail)
        self.scroll.verticalScrollBar().setValue(0)
        if detail.build_context is not None and not detail.build:
            self._build_skeleton = self._build_skeleton_card((30, 92, 74, 86))
            self.content_layout.insertWidget(0, self._build_skeleton)
            self._start_skeleton_pulse(self._build_skeleton)
            self._start_build_load(request_id, detail)
        if detail.art_url:
            self._start_art_load(request_id, detail.art_url)
        else:
            self._set_art_message("Art unavailable")

    def _start_build_load(self, request_id: int, detail: CharacterDetail):
        thread = _BuildLoadThread(detail, self)
        thread.loaded.connect(
            lambda sections: self._on_build_loaded(request_id, sections)
        )
        thread.failed.connect(lambda: self._on_build_failed(request_id))
        thread.finished.connect(lambda t=thread: self._on_build_thread_finished(t))
        self._build_thread = thread
        thread.start()

    def _on_build_thread_finished(self, thread: _BuildLoadThread):
        if self._build_thread is thread:
            self._build_thread = None
        thread.deleteLater()

    def _on_build_loaded(self, request_id: int, sections: list[BuildSection]):
        if request_id != self._request_id or not self.isVisible():
            return
        self._replace_build_skeleton(sections or [])

    def _on_build_failed(self, request_id: int):
        if request_id != self._request_id or not self.isVisible():
            return
        self._replace_build_skeleton([])

    def _replace_build_skeleton(self, sections: list[BuildSection]):
        skeleton = self._build_skeleton
        if skeleton is None:
            return

        scroll_bar = self.scroll.verticalScrollBar()
        old_value = scroll_bar.value()
        old_max = scroll_bar.maximum()
        at_bottom = old_value >= old_max - 2
        request_id = self._request_id

        index = self.content_layout.indexOf(skeleton)
        self._stop_skeleton_pulse()
        self.content_layout.removeWidget(skeleton)
        skeleton.setParent(None)
        skeleton.deleteLater()
        self._build_skeleton = None

        if sections:
            self.content_layout.insertWidget(
                max(index, 0), self._build_build_card(sections)
            )

        if old_value > 0:

            def restore(*_):
                if request_id != self._request_id or not self.isVisible():
                    return
                new_max = scroll_bar.maximum()
                target = (
                    new_max
                    if at_bottom
                    else old_value + (new_max - old_max)
                )
                scroll_bar.setValue(max(0, min(new_max, target)))

            def cleanup():
                try:
                    scroll_bar.rangeChanged.disconnect(restore)
                except (RuntimeError, TypeError):
                    pass

            scroll_bar.rangeChanged.connect(restore)
            QTimer.singleShot(0, restore)
            QTimer.singleShot(150, cleanup)

    def _start_art_load(self, request_id: int, art_url: str):
        thread = _ArtLoadThread(art_url, self)
        thread.loaded.connect(
            lambda data: self._on_art_loaded(request_id, data)
        )
        thread.failed.connect(lambda: self._on_art_failed(request_id))
        thread.finished.connect(lambda t=thread: self._on_art_thread_finished(t))
        self._art_thread = thread
        thread.start()

    def _on_art_thread_finished(self, thread: _ArtLoadThread):
        if self._art_thread is thread:
            self._art_thread = None
        thread.deleteLater()

    def _on_art_loaded(self, request_id: int, data: bytes):
        if request_id != self._request_id or not self.isVisible():
            return
        if self._art_label is None:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self._set_art_message("Art unavailable")
            return
        self._art_label.setText("")
        self._art_label.set_source(pixmap)

    def _on_art_failed(self, request_id: int):
        if request_id != self._request_id or not self.isVisible():
            return
        self._set_art_message("Art unavailable")

    def _set_art_message(self, message: str):
        if self._art_label is not None:
            self._art_label.clear_source()
            self._art_label.setText(message)

    def _on_failed(self, request_id: int, message: str):
        if request_id != self._request_id or not self.isVisible():
            return
        self._clear_content()
        self.art_layout.addWidget(self._build_art_placeholder("Art unavailable"), 1)

        card, layout = self._make_card("Could not load details")
        label = self._label(message, "detailMuted")
        layout.addWidget(label)

        retry = QPushButton("Retry")
        retry.setCursor(Qt.CursorShape.PointingHandCursor)
        retry.clicked.connect(self._retry)
        layout.addWidget(retry, alignment=Qt.AlignmentFlag.AlignLeft)
        self.content_layout.addWidget(card)
        self.content_layout.addStretch(1)

    def _retry(self):
        self._request_id += 1
        request_id = self._request_id
        self._clear_content()
        self._show_loading()
        self._start_load(request_id)

    def _show_loading(self):
        self.art_layout.addWidget(self._build_art_placeholder("Loading art..."), 1)

        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = self._label(
            "Loading fresh details from nanoka.cc...", "detailLoadingLabel"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        skeleton = QWidget()
        skeleton_layout = QVBoxLayout(skeleton)
        skeleton_layout.setContentsMargins(0, 0, 0, 0)
        skeleton_layout.setSpacing(12)
        skeleton_layout.addWidget(self._build_skeleton_card((32, 90, 72, 96)))
        skeleton_layout.addWidget(self._build_skeleton_card((44, 86, 78, 92)))
        skeleton_layout.addWidget(self._build_skeleton_card((28, 88, 82)))
        layout.addWidget(skeleton)

        self.content_layout.addStretch(1)
        self.content_layout.addWidget(wrapper)
        self.content_layout.addStretch(1)
        self._start_skeleton_pulse(skeleton)

    def _clear_content(self):
        self._stop_skeleton_pulse()
        self._build_skeleton = None
        self._art_label = None
        for layout in (self.art_layout, self.content_layout):
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()

    def _build_skeleton_card(self, widths: tuple[int, ...]) -> QFrame:
        card = QFrame()
        card.setObjectName("detailSkeletonCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        for index, width in enumerate(widths):
            layout.addWidget(self._skeleton_line(width, 14 if index == 0 else 10))
        return card

    def _skeleton_line(self, width: int, height: int) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QFrame()
        bar.setObjectName("detailSkeletonBar")
        bar.setFixedHeight(height)
        bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(bar, max(1, width))
        remaining = 100 - width
        if remaining > 0:
            layout.addStretch(remaining)
        return row

    def _start_skeleton_pulse(self, widget: QWidget):
        self._stop_skeleton_pulse()
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(1800)
        animation.setKeyValueAt(0.0, 0.55)
        animation.setKeyValueAt(0.5, 0.95)
        animation.setKeyValueAt(1.0, 0.55)
        animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        animation.setLoopCount(-1)
        animation.start()
        self._skeleton_animation = animation

    def _stop_skeleton_pulse(self):
        animation = self._skeleton_animation
        if animation is None:
            return
        animation.stop()
        animation.deleteLater()
        self._skeleton_animation = None

    def _make_card(self, title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("detailCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        if title:
            heading = QLabel(title)
            heading.setObjectName("detailSectionTitle")
            heading.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(heading)
        return card, layout

    def _label(
        self,
        text: str,
        object_name: str = "",
        *,
        rich: bool = False,
        wrap: bool = True,
    ) -> QLabel:
        label = QLabel(text)
        if object_name:
            label.setObjectName(object_name)
        label.setWordWrap(wrap)
        label.setTextFormat(
            Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText
        )
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def _build_content(self, detail: CharacterDetail):
        self.art_layout.addWidget(self._build_art_panel(detail), 1)
        if detail.build:
            self.content_layout.addWidget(self._build_build_card(detail.build))
        overview = self._build_overview_card(detail)
        if overview is not None:
            self.content_layout.addWidget(overview)
        if detail.stats:
            self.content_layout.addWidget(self._build_stats_card(detail))
        if detail.skills:
            self.content_layout.addWidget(self._build_skills_card(detail))
        if detail.extras:
            self.content_layout.addWidget(self._build_extras_card(detail))
        self.content_layout.addStretch(1)

    def _build_build_card(self, sections: list[BuildSection]) -> QFrame:
        card, layout = self._make_card("Recommended Build")
        note = self._label("Suggested by nanoka.cc", "detailMuted")
        layout.addWidget(note)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        for index, section in enumerate(sections):
            block = QWidget()
            block_layout = QVBoxLayout(block)
            block_layout.setContentsMargins(0, 0, 0, 0)
            block_layout.setSpacing(4)

            heading = QLabel(section.title)
            heading.setObjectName("detailSubheading")
            heading.setTextFormat(Qt.TextFormat.PlainText)
            block_layout.addWidget(heading)
            for item in section.items:
                block_layout.addWidget(self._label(f"• {item}", "detailBuildItem"))
            grid.addWidget(block, index // 2, index % 2, Qt.AlignmentFlag.AlignTop)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        return card

    def _build_art_placeholder(self, text: str) -> QLabel:
        placeholder = QLabel(text)
        placeholder.setObjectName("detailArtPlaceholder")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setWordWrap(True)
        placeholder.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        return placeholder

    def _build_art_panel(self, detail: CharacterDetail) -> QWidget:
        frame = QFrame()
        frame.setObjectName("detailArtFrame")
        grid = QGridLayout(frame)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        art = _ArtLabel()
        art.setObjectName("detailArt")
        art.setText("Loading art...")
        self._art_label = art
        grid.addWidget(art, 0, 0)

        overlay = QFrame()
        overlay.setObjectName("detailArtOverlay")
        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setContentsMargins(14, 14, 14, 14)
        overlay_layout.setSpacing(5)

        name = QLabel(detail.name)
        name.setObjectName("detailArtName")
        name.setTextFormat(Qt.TextFormat.PlainText)
        name.setWordWrap(True)
        overlay_layout.addWidget(name)

        meta = " · ".join(detail.badges)
        if meta:
            meta_label = QLabel(meta)
            meta_label.setObjectName("detailArtMeta")
            meta_label.setTextFormat(Qt.TextFormat.PlainText)
            meta_label.setWordWrap(True)
            overlay_layout.addWidget(meta_label)
        overlay_layout.addStretch(1)
        grid.addWidget(overlay, 0, 0)
        return frame

    def _build_overview_card(self, detail: CharacterDetail) -> QFrame | None:
        subtitle = " · ".join(
            part
            for part in detail.subtitle.split(" · ")
            if part and part not in detail.badges
        )
        if not (subtitle or detail.overview):
            return None

        card, layout = self._make_card("Overview")
        if subtitle:
            layout.addWidget(self._label(subtitle, "detailMuted", rich=True))
        if detail.overview:
            layout.addWidget(self._label(detail.overview, "detailOverview", rich=True))
        return card

    def _build_stats_card(self, detail: CharacterDetail) -> QFrame:
        card, layout = self._make_card(f"Stats · {detail.level_label}")
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)

        for index, (label, value) in enumerate(detail.stats):
            row = index // 2
            column = (index % 2) * 2
            key = QLabel(label)
            key.setObjectName("detailMuted")
            key.setTextFormat(Qt.TextFormat.PlainText)
            val = QLabel(value)
            val.setObjectName("detailStatValue")
            val.setTextFormat(Qt.TextFormat.PlainText)
            grid.addWidget(key, row, column)
            grid.addWidget(val, row, column + 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        layout.addLayout(grid)

        note = self._label(
            "No constellation, sequence, mindscape, or resonance boosts.",
            "detailMuted",
        )
        layout.addWidget(note)
        return card

    def _build_skills_card(self, detail: CharacterDetail) -> QFrame:
        card, layout = self._make_card("Skills")
        note = self._label(
            "Descriptions and multipliers are collapsed. Click a skill to expand.",
            "detailMuted",
        )
        layout.addWidget(note)
        for skill in detail.skills:
            title = f"{skill.name} · {skill.type_name} · Lv. {skill.level}"
            layout.addWidget(_CollapsibleSection(title, self._skill_body(skill)))
        return card

    def _skill_body(self, skill: SkillDetail) -> QWidget:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        if skill.description:
            description = self._label(skill.description, rich=True)
            layout.addWidget(description)

        if skill.multipliers:
            header = QLabel("Multipliers")
            header.setObjectName("detailSubheading")
            header.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(header)

            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(16)
            grid.setVerticalSpacing(4)
            for row, (label, value) in enumerate(skill.multipliers):
                key = QLabel(label)
                key.setObjectName("detailMuted")
                key.setTextFormat(Qt.TextFormat.PlainText)
                key.setWordWrap(True)
                val = QLabel(value)
                val.setObjectName("detailMultiplier")
                val.setTextFormat(Qt.TextFormat.PlainText)
                val.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
                )
                grid.addWidget(key, row, 0)
                grid.addWidget(val, row, 1)
            grid.setColumnStretch(0, 1)
            layout.addLayout(grid)

        return body

    def _build_extras_card(self, detail: CharacterDetail) -> QFrame:
        card, layout = self._make_card("Passives, Traces & More")
        for section in detail.extras:
            layout.addWidget(
                _CollapsibleSection(section.title, self._extra_body(section))
            )
        return card

    def _extra_body(self, section: ExtraSection) -> QWidget:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        for entry in section.entries:
            name = QLabel(entry.name)
            name.setObjectName("detailEntryName")
            name.setTextFormat(Qt.TextFormat.PlainText)
            name.setWordWrap(True)
            layout.addWidget(name)
            if entry.text:
                layout.addWidget(self._label(entry.text, rich=True))
        return body

    def _on_geometry_changed(self, width: int, height: int):
        self.art_column.setFixedWidth(int(width * 0.25))

    def _source_widget(self) -> QWidget | None:
        return self._source

    def _on_close(self):
        self._request_id += 1
        self._clear_content()
        self._game = ""
        self._char_id = ""
        self._source = None

    def showEvent(self, event):
        logger.debug(
            "details showEvent: visible=%s geometry=%s state=%s",
            self.isVisible(),
            self.geometry(),
            self._host.window().windowState(),
        )
        super().showEvent(event)


_popup = None


def open_details(
    game: str,
    char_id: str,
    _char_data=None,
    parent=None,
    source: QWidget | None = None,
):
    """Show the shared character-details popup."""
    global _popup
    if parent is None:
        return
    if isinstance(parent, QMainWindow):
        host = parent.centralWidget() or parent
    else:
        host = parent

    # The module-level popup outlives old host windows; never touch a wrapper
    # whose C++ object is already gone.
    if _popup is not None and not is_alive(_popup):
        _popup = None
    if _popup is not None and _popup._host is not host:
        _popup.close_popup()
        _popup = None
    if _popup is None:
        _popup = CharacterDetailsPopup(host)

    if (
        _popup.isVisible()
        and _popup._game == game
        and _popup._char_id == char_id
    ):
        logger.debug(
            "details already open for %s/%s; raising instead of reloading",
            game,
            char_id,
        )
        _popup.bring_to_front()
        return

    _popup.open_character(game, char_id, source)
