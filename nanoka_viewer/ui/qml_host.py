"""Host helpers that load the QML UI tree into a widget.

The window shell stays a ``QMainWindow`` (title, icon, minimum size,
close-time thread handling), but its central widget is a ``QQuickWidget``
rendering ``nanoka_viewer/qml/Main.qml``.  This module owns the three
environment-sensitive details of that arrangement:

* locating the ``.qml`` files, which sit next to the package in a source
  checkout and are extracted beside the executable in a Nuitka bundle;
* choosing a graphics API that also works on the headless ``offscreen``
  platform the test suite runs on (CI has no GPU either);
* turning QML load failures into loud Python errors instead of a silently
  blank window.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
from PySide6.QtQuickWidgets import QQuickWidget

logger = logging.getLogger(__name__)

# Graphics API selection is process-wide and must happen before the first
# QQuickWindow exists, so it is done once, lazily, on first use.
_GRAPHICS_API_CONFIGURED = False


def qml_dir() -> Path:
    """Return the directory holding the QML sources.

    In a source checkout the files live inside the package.  A Nuitka bundle
    extracts ``--include-data-dir`` entries next to the executable while
    keeping their relative path, and ``__file__`` resolves inside that same
    extracted tree, so the first candidate covers both layouts.  The
    executable-relative candidate is kept for bundles that ship the QML
    payload beside the binary instead.
    """
    candidates = (
        Path(__file__).resolve().parent.parent / "qml",
        Path(QCoreApplication.applicationDirPath()) / "nanoka_viewer" / "qml",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "QML directory not found; looked in: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def qml_file(name: str = "Main.qml") -> Path:
    """Return the path of one QML source, raising if it is missing."""
    path = qml_dir() / name
    if not path.is_file():
        raise FileNotFoundError(f"QML file not found: {path}")
    return path


def _configure_graphics_api() -> None:
    """Pick a rendering backend that works without a GPU.

    The offscreen platform (tests, CI) has no GL/Vulkan context to offer, and
    Qt Quick would rather fail than fall back on its own, so it is pinned to
    the software backend there.  Real displays keep the default RHI path.
    """
    global _GRAPHICS_API_CONFIGURED
    if _GRAPHICS_API_CONFIGURED:
        return
    application = QGuiApplication.instance()
    if application is not None and application.platformName() == "offscreen":
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
    _GRAPHICS_API_CONFIGURED = True


def create_qml_widget(parent=None) -> QQuickWidget:
    """Create a ``QQuickWidget`` hosting ``Main.qml``.

    The widget resizes its root item to its own size, so callers only have to
    place it in a layout.  A failed load raises after logging every QML
    error, because a blank window is much harder to debug than a traceback.
    """
    _configure_graphics_api()

    widget = QQuickWidget(parent)
    widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    widget.setSource(QUrl.fromLocalFile(str(qml_file())))

    if widget.status() != QQuickWidget.Status.Ready:
        details = "\n".join(error.toString() for error in widget.errors())
        logger.error("Failed to load the QML UI:\n%s", details)
        raise RuntimeError(f"Could not load Main.qml:\n{details}")
    return widget
