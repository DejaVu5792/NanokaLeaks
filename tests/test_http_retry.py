"""Tests for the details HTTP retry/backoff policy."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

from nanoka_viewer.api import details as details_api


class FakeResponse:
    def __init__(self, status_code: int = 200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.content = b"payload"
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return self._payload

    def close(self):
        self.closed = True


class HttpRetryTests(unittest.TestCase):
    def setUp(self):
        self._logger_patch = patch.object(details_api.logger, "warning")
        self._logger_patch.start()
        self.addCleanup(self._logger_patch.stop)

    def test_honours_retry_after_and_retries(self):
        responses = [
            FakeResponse(429, headers={"Retry-After": "1.5"}),
            FakeResponse(200, payload={"ok": True}),
        ]
        with (
            patch.object(details_api._session, "get", side_effect=responses) as get,
            patch.object(details_api.time, "sleep") as sleep,
        ):
            result = details_api._get_json("https://example.test/x")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(1.5)
        self.assertTrue(responses[0].closed)

    def test_retries_connection_errors_with_exponential_backoff(self):
        responses = [
            requests.ConnectionError("temporary"),
            FakeResponse(200, payload=[1, 2]),
        ]
        with (
            patch.object(details_api._session, "get", side_effect=responses),
            patch.object(details_api.time, "sleep") as sleep,
            patch.object(details_api.random, "uniform", return_value=0.0),
        ):
            result = details_api._get_json("https://example.test/x")

        self.assertEqual(result, [1, 2])
        sleep.assert_called_once_with(0.5)

    def test_does_not_retry_404(self):
        response = FakeResponse(404)
        with (
            patch.object(details_api._session, "get", return_value=response) as get,
            patch.object(details_api.time, "sleep") as sleep,
        ):
            with self.assertRaises(requests.HTTPError):
                details_api._get_json("https://example.test/missing")

        self.assertEqual(get.call_count, 1)
        sleep.assert_not_called()

    def test_gives_up_after_the_attempt_limit(self):
        responses = [
            FakeResponse(503) for _ in range(details_api._MAX_ATTEMPTS)
        ]
        with (
            patch.object(details_api._session, "get", side_effect=responses) as get,
            patch.object(details_api.time, "sleep") as sleep,
        ):
            with self.assertRaises(requests.HTTPError):
                details_api._get_json("https://example.test/x")

        self.assertEqual(get.call_count, details_api._MAX_ATTEMPTS)
        self.assertEqual(sleep.call_count, details_api._MAX_ATTEMPTS - 1)

    def test_get_bytes_returns_none_after_exhausting_retries(self):
        with (
            patch.object(
                details_api._session,
                "get",
                side_effect=requests.ConnectionError("offline"),
            ) as get,
            patch.object(details_api.time, "sleep"),
        ):
            result = details_api._get_bytes("https://example.test/art.webp")

        self.assertIsNone(result)
        self.assertEqual(get.call_count, details_api._MAX_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
