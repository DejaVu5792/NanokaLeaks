#!/usr/bin/env python3
import sys

from nanoka_viewer.ui import main

import os
import ssl
import time
from pathlib import Path

_SERVER_AUTH_OID = "1.3.6.1.5.5.7.3.1"
_SYSTEM_CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",  # Debian, Ubuntu, Arch
    "/etc/pki/tls/certs/ca-bundle.crt",  # Fedora, RHEL
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # RHEL
    "/etc/ssl/ca-bundle.pem",  # openSUSE
    "/etc/ssl/cert.pem",  # Alpine, macOS
)


def _system_ca_bundle() -> str | None:
    """Return the first usable OS certificate bundle, if any."""
    return next(
        (path for path in _SYSTEM_CA_BUNDLES if Path(path).is_file()),
        None,
    )


def _windows_ca_bundle() -> str | None:
    """Export the Windows root/intermediate stores to a PEM file, cached daily."""
    target = Path.home() / ".cache" / "nanoka_leaks" / "ca-bundle.pem"
    try:
        if target.is_file() and time.time() - target.stat().st_mtime < 86400:
            return str(target)
        pems: list[str] = []
        for store in ("ROOT", "CA"):
            for der, encoding, trust in ssl.enum_certificates(store):
                usable = trust is True or (
                    isinstance(trust, (set, frozenset))
                    and _SERVER_AUTH_OID in trust
                )
                if encoding == "x509_asn" and usable:
                    pems.append(ssl.DER_cert_to_PEM_cert(der))
        if not pems:
            return None
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".tmp")
        temp.write_text("".join(pems), encoding="ascii")
        os.replace(temp, target)
        return str(target)
    except Exception:
        return None


def _ensure_ca_bundle() -> None:
    try:
        import certifi

        if Path(certifi.where()).is_file():
            return
    except Exception:
        pass

    if sys.platform == "win32":
        bundle = _windows_ca_bundle()
    else:
        bundle = _system_ca_bundle()
    if bundle:
        os.environ.setdefault("SSL_CERT_FILE", bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", bundle)


_ensure_ca_bundle()

if __name__ == "__main__":
    sys.exit(main())
