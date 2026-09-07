"""Tests for the shared API client's retry/backoff behavior."""

import io
import unittest
import urllib.error
from unittest.mock import patch, MagicMock

from btc_toolkit.api import (
    get_json, get_api_base, set_api_base,
    MempoolAPIError, NotFoundError,
)


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://mempool.space/api/x", code=code,
        msg="err", hdrs=None, fp=io.BytesIO(b""),
    )


def _ok_response(body: bytes = b'{"ok": true}') -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestRetry(unittest.TestCase):
    @patch("btc_toolkit.api.time.sleep")
    @patch("btc_toolkit.api.urllib.request.urlopen")
    def test_retries_on_429_then_succeeds(self, mock_open, mock_sleep):
        mock_open.side_effect = [_http_error(429), _ok_response()]
        result = get_json("/x")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(mock_open.call_count, 2)
        mock_sleep.assert_called_once_with(0.5)

    @patch("btc_toolkit.api.time.sleep")
    @patch("btc_toolkit.api.urllib.request.urlopen")
    def test_retries_on_503_with_backoff(self, mock_open, mock_sleep):
        mock_open.side_effect = [_http_error(503), _http_error(503), _ok_response()]
        result = get_json("/x")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(mock_open.call_count, 3)
        # Exponential backoff: 0.5s then 1.0s
        self.assertEqual(
            [c.args[0] for c in mock_sleep.call_args_list], [0.5, 1.0]
        )

    @patch("btc_toolkit.api.time.sleep")
    @patch("btc_toolkit.api.urllib.request.urlopen")
    def test_gives_up_after_max_attempts(self, mock_open, mock_sleep):
        mock_open.side_effect = [_http_error(503)] * 3
        with self.assertRaises(MempoolAPIError):
            get_json("/x")
        self.assertEqual(mock_open.call_count, 3)

    @patch("btc_toolkit.api.time.sleep")
    @patch("btc_toolkit.api.urllib.request.urlopen")
    def test_404_never_retried(self, mock_open, mock_sleep):
        mock_open.side_effect = [_http_error(404)]
        with self.assertRaises(NotFoundError):
            get_json("/x")
        self.assertEqual(mock_open.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("btc_toolkit.api.time.sleep")
    @patch("btc_toolkit.api.urllib.request.urlopen")
    def test_400_never_retried(self, mock_open, mock_sleep):
        mock_open.side_effect = [_http_error(400)]
        with self.assertRaises(MempoolAPIError):
            get_json("/x")
        self.assertEqual(mock_open.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("btc_toolkit.api.time.sleep")
    @patch("btc_toolkit.api.urllib.request.urlopen")
    def test_connection_error_retried(self, mock_open, mock_sleep):
        mock_open.side_effect = [
            urllib.error.URLError("timed out"), _ok_response()
        ]
        result = get_json("/x")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(mock_open.call_count, 2)


class TestNetworksAndCustomBase(unittest.TestCase):
    def tearDown(self):
        set_api_base(None)  # never leak the override to other tests

    def test_signet_base(self):
        self.assertEqual(
            get_api_base("signet"), "https://mempool.space/signet/api"
        )

    def test_mainnet_and_testnet_presets(self):
        self.assertEqual(get_api_base("mainnet"), "https://mempool.space/api")
        self.assertEqual(
            get_api_base("testnet"), "https://mempool.space/testnet/api"
        )

    def test_unsupported_network_raises(self):
        with self.assertRaises(ValueError):
            get_api_base("regtest")

    def test_custom_base_overrides_network(self):
        set_api_base("http://umbrel.local:3006/api")
        self.assertEqual(get_api_base("mainnet"), "http://umbrel.local:3006/api")
        self.assertEqual(get_api_base("signet"), "http://umbrel.local:3006/api")

    def test_custom_base_strips_trailing_slash(self):
        set_api_base("http://my-node.example/api/")
        self.assertEqual(get_api_base("mainnet"), "http://my-node.example/api")

    def test_reset_restores_presets(self):
        set_api_base("http://x.local/api")
        set_api_base(None)
        self.assertEqual(get_api_base("mainnet"), "https://mempool.space/api")

    @patch("btc_toolkit.api.time.sleep")
    @patch("btc_toolkit.api.urllib.request.urlopen")
    def test_custom_base_used_in_requests(self, mock_open, mock_sleep):
        set_api_base("http://node.home:3006/api")
        mock_open.side_effect = [_ok_response()]
        get_json("/blocks/tip/height")
        called_url = mock_open.call_args.args[0].full_url
        self.assertTrue(called_url.startswith("http://node.home:3006/api/"))


if __name__ == "__main__":
    unittest.main()