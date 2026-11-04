"""Regression tests for the frozen-build TLS trust store fallback.

Nuitka onefile builds used to ship ``certifi`` without its ``cacert.pem`` data
file, so the first HTTPS request failed with::

    OSError: Could not find a suitable TLS CA certificate bundle,
    invalid path: /tmp/onefile_.../certifi/cacert.pem

``main._ensure_ca_bundle`` now falls back to the operating system's trust
store when the bundled certifi file is unavailable.  These tests pin that
behaviour down without needing a compiled binary.
"""

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import main as app_main
from support import DETAILS_ROOT


def _certifi(path: Path):
    return types.SimpleNamespace(where=lambda: str(path))


class SystemBundleTests(unittest.TestCase):
    def test_returns_first_existing_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.crt"
            usable = Path(tmp) / "ca-bundle.crt"
            usable.write_text("pem", encoding="ascii")
            with patch.object(
                app_main,
                "_SYSTEM_CA_BUNDLES",
                (str(missing), str(usable)),
            ):
                self.assertEqual(app_main._system_ca_bundle(), str(usable))

    def test_returns_none_when_no_candidate_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(
                app_main,
                "_SYSTEM_CA_BUNDLES",
                (str(Path(tmp) / "missing.crt"),),
            ):
                self.assertIsNone(app_main._system_ca_bundle())


class EnsureCaBundleTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ, {}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_keeps_a_valid_bundled_certifi_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "cacert.pem"
            bundle.write_text("pem", encoding="ascii")
            with patch.dict(sys.modules, {"certifi": _certifi(bundle)}):
                app_main._ensure_ca_bundle()

        self.assertNotIn("SSL_CERT_FILE", os.environ)
        self.assertNotIn("REQUESTS_CA_BUNDLE", os.environ)

    def test_uses_the_system_bundle_when_certifi_data_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "ca-bundle.crt"
            bundle.write_text("pem", encoding="ascii")
            with (
                patch.dict(
                    sys.modules,
                    {"certifi": _certifi(Path(tmp) / "missing.pem")},
                ),
                patch.object(app_main.sys, "platform", "linux"),
                patch.object(
                    app_main, "_system_ca_bundle", return_value=str(bundle)
                ),
            ):
                app_main._ensure_ca_bundle()

        self.assertEqual(os.environ["SSL_CERT_FILE"], str(bundle))
        self.assertEqual(os.environ["REQUESTS_CA_BUNDLE"], str(bundle))

    def test_uses_the_windows_store_when_certifi_data_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "ca-bundle.pem"
            bundle.write_text("pem", encoding="ascii")
            with (
                patch.dict(
                    sys.modules,
                    {"certifi": _certifi(Path(tmp) / "missing.pem")},
                ),
                patch.object(app_main.sys, "platform", "win32"),
                patch.object(
                    app_main, "_windows_ca_bundle", return_value=str(bundle)
                ),
            ):
                app_main._ensure_ca_bundle()

        self.assertEqual(os.environ["REQUESTS_CA_BUNDLE"], str(bundle))

    def test_leaves_the_environment_alone_when_no_bundle_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.dict(
                    sys.modules,
                    {"certifi": _certifi(Path(tmp) / "missing.pem")},
                ),
                patch.object(app_main.sys, "platform", "linux"),
                patch.object(app_main, "_system_ca_bundle", return_value=None),
            ):
                app_main._ensure_ca_bundle()

        self.assertNotIn("SSL_CERT_FILE", os.environ)
        self.assertNotIn("REQUESTS_CA_BUNDLE", os.environ)


class WindowsCaBundleTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)

    def test_exports_server_auth_certificates_and_reuses_the_cache(self):
        stores = []

        def fake_enum(store):
            stores.append(store)
            if store != "ROOT":
                return []
            return [
                (b"root", "x509_asn", True),
                (b"server", "x509_asn", {app_main._SERVER_AUTH_OID}),
                (b"client", "x509_asn", {"1.3.6.1.5.5.7.3.2"}),
            ]

        with (
            patch.object(app_main.Path, "home", return_value=self.home),
            patch.object(
                app_main.ssl,
                "enum_certificates",
                side_effect=fake_enum,
                create=True,
            ),
            patch.object(
                app_main.ssl,
                "DER_cert_to_PEM_cert",
                side_effect=lambda der: f"<{der.decode()}>",
            ),
        ):
            first = app_main._windows_ca_bundle()
            second = app_main._windows_ca_bundle()

        self.assertIsNotNone(first)
        self.assertEqual(first, second)
        self.assertEqual(stores, ["ROOT", "CA"])
        self.assertEqual(Path(first).read_text(encoding="ascii"), "<root><server>")

    def test_returns_none_when_no_certificates_are_usable(self):
        with (
            patch.object(app_main.Path, "home", return_value=self.home),
            patch.object(
                app_main.ssl,
                "enum_certificates",
                return_value=[],
                create=True,
            ),
        ):
            self.assertIsNone(app_main._windows_ca_bundle())


class PackagingTests(unittest.TestCase):
    def test_nuitka_flags_ship_certifi_package_data(self):
        flags = (
            Path(DETAILS_ROOT) / "packaging" / "nuitka_flags.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("--include-package-data=certifi", flags)


if __name__ == "__main__":
    unittest.main()
