"""Open character pages in the user's default browser.

The in-app browser (QtWebEngine) was removed from the app, so a card's
external-link button hands the URL to the desktop instead.  On Linux this
prefers the configured default web browser through ``gtk-launch`` (which
also works for Flatpak/snap browsers that ``webbrowser`` cannot find);
everywhere else it falls back to :mod:`webbrowser`.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import webbrowser

logger = logging.getLogger(__name__)


def open_external_url(url: str) -> None:
    """Open *url* in the system default browser."""
    if not url:
        return

    if sys.platform.startswith("linux"):
        try:
            desktop = subprocess.check_output(
                ["xdg-settings", "get", "default-web-browser"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if desktop:
                subprocess.Popen(
                    ["gtk-launch", desktop, url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return
        except Exception:
            logger.debug("gtk-launch unavailable; falling back to webbrowser")

    webbrowser.open(url, new=2)
