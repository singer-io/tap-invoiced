"""Unit tests for tap_invoiced entry point and SDK error behaviour.

Covers: main() dispatch (discover / sync), config key validation,
SDK error propagation through fetch_with_backoff_retry.
All external calls are mocked — no real network traffic.
"""
import json
import unittest
from unittest.mock import patch, MagicMock, call

from invoiced.errors import ApiConnectionError, ApiError, RateLimitError

from tap_invoiced.sync import fetch_with_backoff_retry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**kwargs):
    base = {
        "api_key": "test_api_key",
        "start_date": "2020-01-01T00:00:00Z",
    }
    base.update(kwargs)
    return base


def _make_mock_args(discover=False, catalog=None, config=None, state=None):
    args = MagicMock()
    args.discover = discover
    args.catalog = catalog
    args.config = config or _make_config()
    args.state = state or {}
    return args


# ---------------------------------------------------------------------------
# TestMainDispatch
# ---------------------------------------------------------------------------

class TestMainDispatch(unittest.TestCase):
    """main() correctly routes CLI flags to discover or sync code paths."""

    @patch("tap_invoiced.discover_streams")
    @patch("tap_invoiced.utils.parse_args")
    def test_discover_flag_calls_discover_streams(self, mock_parse_args, mock_discover):
        """main() calls discover_streams() and prints JSON when --discover is set."""
        mock_parse_args.return_value = _make_mock_args(discover=True)
        mock_discover.return_value = {"streams": []}

        from tap_invoiced import main
        with patch("builtins.print") as mock_print:
            main()

        mock_discover.assert_called_once()

    @patch("tap_invoiced.discover_streams")
    @patch("tap_invoiced.utils.parse_args")
    def test_discover_prints_json_to_stdout(self, mock_parse_args, mock_discover):
        """main() prints the catalog as JSON when --discover is set."""
        mock_parse_args.return_value = _make_mock_args(discover=True)
        catalog = {"streams": [{"tap_stream_id": "customers"}]}
        mock_discover.return_value = catalog

        from tap_invoiced import main
        captured = {}
        with patch("builtins.print", side_effect=lambda x: captured.update({"out": x})):
            main()

        out = captured.get("out", "")
        parsed = json.loads(out)
        self.assertEqual(catalog, parsed)

    @patch("tap_invoiced.sync_streams")
    @patch("tap_invoiced.utils.parse_args")
    def test_catalog_flag_calls_sync_streams(self, mock_parse_args, mock_sync):
        """main() calls sync_streams() when --catalog is provided."""
        mock_parse_args.return_value = _make_mock_args(
            discover=False,
            catalog=MagicMock(),
        )

        from tap_invoiced import main
        main()

        mock_sync.assert_called_once()

    @patch("tap_invoiced.sync_streams")
    @patch("tap_invoiced.utils.parse_args")
    def test_sync_streams_receives_config_state_catalog(self, mock_parse_args, mock_sync):
        """main() passes config, state, and catalog to sync_streams()."""
        cfg = _make_config()
        state = {"bookmarks": {}}
        cat = MagicMock()
        mock_parse_args.return_value = _make_mock_args(
            discover=False, catalog=cat, config=cfg, state=state
        )

        from tap_invoiced import main
        main()

        mock_sync.assert_called_once_with(cfg, state, cat)

    @patch("tap_invoiced.sync_streams")
    @patch("tap_invoiced.discover_streams")
    @patch("tap_invoiced.utils.parse_args")
    def test_neither_flag_calls_neither_function(
        self, mock_parse_args, mock_discover, mock_sync
    ):
        """main() does nothing when neither --discover nor --catalog is supplied."""
        mock_parse_args.return_value = _make_mock_args(discover=False, catalog=None)

        from tap_invoiced import main
        main()

        mock_discover.assert_not_called()
        mock_sync.assert_not_called()

    @patch("tap_invoiced.sync_streams")
    @patch("tap_invoiced.utils.parse_args")
    def test_exception_in_sync_streams_is_reraised(self, mock_parse_args, mock_sync):
        """main() re-raises exceptions from sync_streams() after logging."""
        mock_parse_args.return_value = _make_mock_args(
            discover=False,
            catalog=MagicMock(),
        )
        mock_sync.side_effect = RuntimeError("sync failed")

        from tap_invoiced import main
        with self.assertRaises(RuntimeError):
            main()


# ---------------------------------------------------------------------------
# TestRequiredConfigKeys
# ---------------------------------------------------------------------------

class TestRequiredConfigKeys(unittest.TestCase):
    """REQUIRED_CONFIG_KEYS is correctly defined in the tap module."""

    def test_required_keys_are_declared(self):
        """tap_invoiced declares start_date and api_key as required config keys."""
        import tap_invoiced
        self.assertIn("start_date", tap_invoiced.REQUIRED_CONFIG_KEYS)
        self.assertIn("api_key", tap_invoiced.REQUIRED_CONFIG_KEYS)

    def test_required_keys_is_a_list(self):
        """REQUIRED_CONFIG_KEYS is a list."""
        import tap_invoiced
        self.assertIsInstance(tap_invoiced.REQUIRED_CONFIG_KEYS, list)

    def test_exactly_two_required_keys(self):
        """Exactly two config keys are required (start_date and api_key)."""
        import tap_invoiced
        self.assertEqual(2, len(tap_invoiced.REQUIRED_CONFIG_KEYS))


# ---------------------------------------------------------------------------
# TestSdkErrorPropagation
# ---------------------------------------------------------------------------

class TestSdkErrorPropagation(unittest.TestCase):
    """fetch_with_backoff_retry() propagates Invoiced SDK errors after retries.

    We call the innermost wrapped function directly to bypass backoff delay in tests.
    """

    def _unwrap(self, fn):
        """Recursively unwrap backoff-decorated functions to access the raw callable."""
        inner = fn
        while hasattr(inner, "__wrapped__"):
            inner = inner.__wrapped__
        return inner

    def test_api_error_propagates_from_wrapped_function(self):
        """The unwrapped function raises ApiError when sdkObject.list() fails."""
        raw = self._unwrap(fetch_with_backoff_retry)
        sdk_obj = MagicMock()
        sdk_obj.list.side_effect = ApiError("server error")
        with self.assertRaises(ApiError):
            raw(sdk_obj, page=1, bookmark=0)

    def test_api_connection_error_propagates_from_wrapped_function(self):
        """The unwrapped function raises ApiConnectionError on connectivity failure."""
        raw = self._unwrap(fetch_with_backoff_retry)
        sdk_obj = MagicMock()
        sdk_obj.list.side_effect = ApiConnectionError("connection lost")
        with self.assertRaises(ApiConnectionError):
            raw(sdk_obj, page=1, bookmark=0)

    def test_rate_limit_error_propagates_from_wrapped_function(self):
        """The unwrapped function raises RateLimitError on HTTP 429."""
        raw = self._unwrap(fetch_with_backoff_retry)
        sdk_obj = MagicMock()
        sdk_obj.list.side_effect = RateLimitError("rate limited")
        with self.assertRaises(RateLimitError):
            raw(sdk_obj, page=1, bookmark=0)

    def test_no_error_returns_correct_tuple(self):
        """The unwrapped function returns (objects, metadata) on success."""
        raw = self._unwrap(fetch_with_backoff_retry)
        sdk_obj = MagicMock()
        list_meta = MagicMock()
        list_meta.links = {}
        sdk_obj.list.return_value = (["rec1", "rec2"], list_meta)

        objects, meta = raw(sdk_obj, page=1, bookmark=0)
        self.assertEqual(["rec1", "rec2"], objects)
        self.assertIs(list_meta, meta)

    def test_unexpected_exception_propagates_unchanged(self):
        """Non-SDK exceptions propagate without modification."""
        raw = self._unwrap(fetch_with_backoff_retry)
        sdk_obj = MagicMock()
        sdk_obj.list.side_effect = ValueError("unexpected")
        with self.assertRaises(ValueError):
            raw(sdk_obj, page=1, bookmark=0)


# ---------------------------------------------------------------------------
# TestFetchWithBackoffRetryIntegration
# ---------------------------------------------------------------------------

class TestFetchWithBackoffRetryIntegration(unittest.TestCase):
    """Integration-level tests for fetch_with_backoff_retry() via the decorated API."""

    def test_decorated_function_succeeds_on_first_try(self):
        """fetch_with_backoff_retry() immediately returns when sdkObject.list() succeeds."""
        sdk_obj = MagicMock()
        list_meta = MagicMock()
        list_meta.links = {"next": "..."}
        sdk_obj.list.return_value = ([], list_meta)

        objects, meta = fetch_with_backoff_retry(sdk_obj, 1, 0)
        self.assertIs(list_meta, meta)
        self.assertEqual(1, sdk_obj.list.call_count)

    def test_decorated_function_passes_page_and_bookmark(self):
        """fetch_with_backoff_retry() forwards page and updated_after to sdkObject.list()."""
        sdk_obj = MagicMock()
        sdk_obj.list.return_value = ([], MagicMock(links={}))

        fetch_with_backoff_retry(sdk_obj, 3, 1609459200)
        self.assertEqual(3,          sdk_obj.list.call_args[1]["page"])
        self.assertEqual(1609459200, sdk_obj.list.call_args[1]["updated_after"])


if __name__ == "__main__":
    unittest.main()
