"""Shared HTTP session for every network path.

Details, builds, artwork and images all talk to the same host, so they share
one pooled session.  Besides connection reuse this keeps the User-Agent (and
the retry/pool settings) in one place instead of drifting per module.
"""

from __future__ import annotations

import threading

import requests
from requests.adapters import HTTPAdapter

from .constants import USER_AGENT

POOL_CONNECTIONS = 16
POOL_MAXSIZE = 32

_session: requests.Session | None = None
_lock = threading.Lock()


def get_session() -> requests.Session:
    """Return the process-wide pooled session, creating it on first use."""
    global _session
    if _session is None:
        with _lock:
            if _session is None:
                session = requests.Session()
                session.headers["User-Agent"] = USER_AGENT
                adapter = HTTPAdapter(
                    pool_connections=POOL_CONNECTIONS,
                    pool_maxsize=POOL_MAXSIZE,
                    max_retries=1,
                )
                session.mount("https://", adapter)
                session.mount("http://", adapter)
                _session = session
    return _session


# Import-time alias so modules can keep a stable module-level name (tests patch
# ``details._session`` and ``manifest.session`` directly).
session = get_session()
