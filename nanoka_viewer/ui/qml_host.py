"""Host helpers that load the QML UI tree into a widget.

The window shell stays a ``QMainWindow`` (title, icon, minimum size,
close-time thread handling), but its central widget is a ``QQuickWidget``
rendering ``nanoka_viewer/qml/Main.qml``.  This module owns the
environment-sensitive details of that arrangement:

* locating the ``.qml`` files, which sit next to the package in a source
  checkout and are extracted beside the executable in a Nuitka bundle;
* choosing a graphics API that also works on the headless ``offscreen``
  platform the test suite runs on (CI has no GPU either);
* registering the ``image://nanoka`` provider and the Python context objects
  (``viewer``, ``sections``) *before* the tree is parsed, because the
  bindings are evaluated during loading;
* turning QML load failures into loud Python errors instead of a silently
  blank window.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtQuickWidgets import QQuickWidget

from .image_provider import PROVIDER_ID, NanokaImageProvider

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


def create_qml_widget(
    parent=None,
    context_properties=None,
    *,
    source: str = "Main.qml",
    image_providers=None,
    translucent: bool = False,
) -> QQuickWidget:
    """Create a ``QQuickWidget`` hosting one of the QML trees.

    The widget resizes its root item to its own size, so callers only have to
    place it in a layout.  *context_properties* maps names to Python objects
    exposed to the QML tree (``viewer`` and ``sections`` for the real window,
    ``details`` or ``settings`` for a popup).

    *source* is relative to the QML directory; *image_providers* adds
    ``image://`` providers beside the shared ``image://nanoka`` one.
    *translucent* lets the widget composite over what is behind it, which the
    popups need so their rounded corners show the dimmed backdrop.

    Everything the tree needs is registered *before* ``setSource``: QML
    evaluates bindings while loading, so a context property added afterwards
    would already have produced "undefined" warnings.

    A failed load raises after logging every QML error, because a blank
    window is much harder to debug than a traceback.
    """
    _configure_graphics_api()

    # Fusion matches the QWidget chrome and the popups; only set it before
    # the first engine resolves a style, otherwise Qt warns on every window.
    if not QQuickStyle.name():
        QQuickStyle.setStyle("Fusion")

    widget = QQuickWidget(parent)
    widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    if translucent:
        widget.setClearColor(Qt.GlobalColor.transparent)
        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    widget.engine().addImageProvider(PROVIDER_ID, NanokaImageProvider())
    for provider_id, provider in (image_providers or {}).items():
        widget.engine().addImageProvider(provider_id, provider)
    for name, value in (context_properties or {}).items():
        widget.rootContext().setContextProperty(name, value)
    widget.setSource(QUrl.fromLocalFile(str(qml_file(source))))

    if widget.status() != QQuickWidget.Status.Ready:
        details = "\n".join(error.toString() for error in widget.errors())
        logger.error("Failed to load %s:\n%s", source, details)
        raise RuntimeError(f"Could not load {source}:\n{details}")
    return widget
