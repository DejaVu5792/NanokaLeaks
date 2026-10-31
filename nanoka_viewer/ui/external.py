"""Open character pages in the user's default browser."""

from __future__ import annotations

import logging
import webbrowser

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = {"http", "https"}


def open_external_url(url: str) -> None:
    """Open *url* in the system default browser."""
    if not url:
        return

    qurl = QUrl(url)
    if not qurl.isValid() or qurl.scheme().lower() not in _ALLOWED_SCHEMES:
        logger.warning("Refusing to open non-web URL: %s", url)
        return

    # Windows: ShellExecute, macOS: NSWorkspace, Linux: xdg-desktop-portal
    # (or xdg-open when no portal is running).
    if QDesktopServices.openUrl(qurl):
        return

    logger.debug("QDesktopServices failed; falling back to webbrowser")
    if not webbrowser.open(url, new=2):
        logger.warning("Could not open %s in a browser", url)
