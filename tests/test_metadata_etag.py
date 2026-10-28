"""Tests for ETag revalidation of the shared build tables."""

from __future__ import annotations

import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from nanoka_viewer.api import details as details_api


class FakeResponse:
    def __init__(self, status_code: int = 200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return self._payload

    def close(self):
        self.closed = True


class MetadataEtagTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.cache_dir = Path(self._temp.name)

        self._metadata_cache = details_api._metadata_cache
        details_api._metadata_cache = {}
        self.addCleanup(self._restore_cache)

        self.record = Mock()
        self._patches = [
            patch.object(details_api, "METADATA_CACHE_DIR", self.cache_dir),
            patch.object(details_api, "get_setting", return_value=True),
            patch.object(
                details_api, "record_build_cache_write", self.record
            ),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.cache_key = ("hsr", "1.0", "relicset")
        self.disk_path = details_api._metadata_disk_path(self.cache_key)
        self.etag_path = details_api._metadata_etag_path(self.cache_key)

    def _restore_cache(self):
        details_api._metadata_cache = self._metadata_cache

    def _store_old(self):
        self.disk_path.write_bytes(pickle.dumps({"old": True}))
        self.etag_path.write_text('"old-etag"', encoding="utf-8")

    def _call(self):
        return details_api._fetch_metadata_file(
            "hsr", "1.0", "relicset", "https://example.test/relicset.json", refresh=True
        )

    def test_304_reuses_the_cached_table(self):
        self._store_old()
        response = FakeResponse(304, headers={"ETag": '"old-etag"'})

        with patch.object(
            details_api, "_request_with_retries", return_value=response
        ) as request:
            data = self._call()

        self.assertEqual(data, {"old": True})
        request.assert_called_once_with(
            "https://example.test/relicset.json",
            headers={"If-None-Match": '"old-etag"'},
        )
        self.assertTrue(response.closed)
        self.assertEqual(
            details_api._metadata_cache[self.cache_key], {"old": True}
        )
        self.record.assert_not_called()

    def test_200_replaces_the_cached_table_and_etag(self):
        self._store_old()
        response = FakeResponse(
            200, payload={"new": True}, headers={"ETag": '"new-etag"'}
        )

        with patch.object(
            details_api, "_request_with_retries", return_value=response
        ):
            data = self._call()

        self.assertEqual(data, {"new": True})
        self.assertEqual(pickle.loads(self.disk_path.read_bytes()), {"new": True})
        self.assertEqual(
            self.etag_path.read_text(encoding="utf-8"), '"new-etag"'
        )
        self.record.assert_called_once()

    def test_refresh_without_etag_does_a_full_fetch(self):
        self.disk_path.write_bytes(pickle.dumps({"old": True}))
        response = FakeResponse(
            200, payload={"fresh": True}, headers={"ETag": '"fresh-etag"'}
        )

        with patch.object(
            details_api, "_request_with_retries", return_value=response
        ) as request:
            data = self._call()

        self.assertEqual(data, {"fresh": True})
        request.assert_called_once_with(
            "https://example.test/relicset.json", headers=None
        )
        self.assertEqual(
            pickle.loads(self.disk_path.read_bytes()), {"fresh": True}
        )
        self.assertEqual(
            self.etag_path.read_text(encoding="utf-8"), '"fresh-etag"'
        )

    def test_normal_fetch_stores_an_etag_for_later_revalidation(self):
        response = FakeResponse(
            200, payload={"table": True}, headers={"ETag": '"stored-etag"'}
        )

        with patch.object(
            details_api, "_request_with_retries", return_value=response
        ):
            data = details_api._fetch_metadata_file(
                "hsr", "1.0", "relicset", "https://example.test/relicset.json"
            )

        self.assertEqual(data, {"table": True})
        self.assertEqual(
            self.etag_path.read_text(encoding="utf-8"), '"stored-etag"'
        )
        self.record.assert_called_once()

    def test_reset_clears_only_the_memory_cache(self):
        self._store_old()
        details_api._metadata_cache[self.cache_key] = {"old": True}

        details_api.reset_build_cache()

        self.assertEqual(details_api._metadata_cache, {})
        self.assertTrue(self.disk_path.exists())
        self.assertTrue(self.etag_path.exists())


if __name__ == "__main__":
    unittest.main()
