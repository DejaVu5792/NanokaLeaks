"""Main application entry point for the Kirigami/QML-based Nanoka Viewer."""

import logging
import os
import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtQml import QQmlApplicationEngine

from .backend import NanokaBackend

logger = logging.getLogger(__name__)


def _app_icon() -> QIcon:
    candidates = (
        Path(QCoreApplication.applicationDirPath()) / "nanokaleaks.png",
        Path(__file__).resolve().parent.parent / "assets" / "nanokaleaks.png",
    )
    for candidate in candidates:
        if candidate.is_file():
            return QIcon(str(candidate))
    return QIcon()


def main(argv=None):
    """Main entry point for the application."""
    import argparse

    parser = argparse.ArgumentParser(prog="NanokaLeaks", description="Nanoka Viewer")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    args, remaining = parser.parse_known_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    return _run_app(remaining)


def _run_app(argv):
    """Create and run the QML application."""
    # Qt requires QGuiApplication (not QApplication) for QML-only apps
    app = QGuiApplication(argv if argv else sys.argv)
    app.setApplicationName("NanokaLeaks")
    app.setDesktopFileName("nanokaleaks")
    icon = _app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    engine = QQmlApplicationEngine()
    # Add system QML path for Kirigami
    engine.addImportPath("/usr/lib/qt6/qml")

    # Create and expose the backend
    backend = NanokaBackend()
    engine.rootContext().setContextProperty("backend", backend)

    # Load the main QML file
    qml_file = Path(__file__).parent / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))

    if not engine.rootObjects():
        logger.critical("Failed to load QML: %s", qml_file)
        sys.exit(-1)

    # Trigger initial data load
    backend.loadData()

    return app.exec()


if __name__ == "__main__":
    main()
