import unittest
from unittest.mock import patch, MagicMock
from invoiced.errors import ApiConnectionError, ApiError, RateLimitError
from tap_invoiced.sync import sync, STREAM_SDK_OBJECTS


class TestSyncBackoff(unittest.TestCase):
    @patch("time.sleep", return_value=None)
    def test_sync_retries_on_server_error(self, _):
        client = MagicMock()
        sdk_obj = MagicMock()
        # Create a mock invoiced.erros.ApiError with status_code = 500
        http_error = ApiError(message="Internal Server Error", status_code=500)
        sdk_obj.list.side_effect = [
            http_error,
            http_error,
            http_error,
            http_error,
            ([], MagicMock(links={}))
        ]

        setattr(client, STREAM_SDK_OBJECTS["credit_notes"], sdk_obj)
        sync(client, {"start_date": "2020-01-01"}, {}, "credit_notes", {}, {})
        self.assertGreaterEqual(sdk_obj.list.call_count, 5)

    @patch("time.sleep", return_value=None)
    def test_sync_succeeds_after_retries(self, _):
        client = MagicMock()
        sdk_obj = MagicMock()
        # Create a mock invoiced.erros.ApiError with status_code = 500
        http_error = ApiError(message="Temporary 500 error", status_code=500)

        # Make the list method raise twice, then succeed
        sdk_obj.list.side_effect = [
            http_error,
            http_error,
            ([], MagicMock(links={}))
        ]
        setattr(client, STREAM_SDK_OBJECTS["credit_notes"], sdk_obj)

        # Call sync and verify retries happen
        sync(client, {"start_date": "2020-01-01"}, {}, "credit_notes", {}, {})
        self.assertEqual(sdk_obj.list.call_count, 3)

    @patch("time.sleep", return_value=None)
    def test_sync_raises_runtime_error_immediately(self, _):
        client = MagicMock()
        sdk_obj = MagicMock()
        sdk_obj.list.side_effect = RuntimeError("Unexpected error")
        setattr(client, STREAM_SDK_OBJECTS["credit_notes"], sdk_obj)
        with self.assertRaises(RuntimeError):
            sync(client, {"start_date": "2020-01-01"}, {}, "credit_notes", {}, {})
        self.assertEqual(sdk_obj.list.call_count, 1)

    @patch("time.sleep", return_value=None)
    def test_connection_error(self, _):
        client = MagicMock()
        sdk_obj = MagicMock()
        sdk_obj.list.side_effect = ApiConnectionError(message="Connection Error")
        setattr(client, STREAM_SDK_OBJECTS["credit_notes"], sdk_obj)

        with self.assertRaises(ApiConnectionError):
            sync(client, {"start_date": "2020-01-01"}, {}, "credit_notes", {}, {})

        self.assertEqual(sdk_obj.list.call_count, 5)

    @patch("time.sleep", return_value=None)
    def test_sync_retries_on_rate_limit_error(self, _):
        client = MagicMock()
        sdk_obj = MagicMock()
        http_error = RateLimitError(message="Rate Limit Error", status_code=429)
        sdk_obj.list.side_effect = [http_error] * 5
        setattr(client, STREAM_SDK_OBJECTS["credit_notes"], sdk_obj)

        with self.assertRaises(Exception):
            sync(client, {"start_date": "2020-01-01"}, {}, "credit_notes", {}, {})

        self.assertEqual(sdk_obj.list.call_count, 5)
