import unittest
from unittest.mock import patch, MagicMock
import requests
from tap_invoiced.sync import Server5xxError
from tap_invoiced.sync import sync, STREAM_SDK_OBJECTS


class TestSyncBackoff(unittest.TestCase):

    @patch("time.sleep", return_value=None)
    def test_sync_retries_on_server_error(self, _):
        client = MagicMock()
        sdk_obj = MagicMock()

        # Create a mock response with 500 error
        mock_response = MagicMock()
        mock_response.status_code = 500
        http_error = requests.exceptions.HTTPError(response=mock_response)

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
        sdk_obj.list.side_effect = [
            requests.exceptions.HTTPError("Temporary 500 error"),
            requests.exceptions.HTTPError("Temporary 500 error"),
            ([], MagicMock(links={}))
        ]
        setattr(client, STREAM_SDK_OBJECTS["credit_notes"], sdk_obj)
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
    def test_sync_raises_after_max_retries(self, _):
        client = MagicMock()
        sdk_obj = MagicMock()
        sdk_obj.list.side_effect = [requests.exceptions.HTTPError()] * 5
        setattr(client, STREAM_SDK_OBJECTS["credit_notes"], sdk_obj)
        with self.assertRaises(requests.exceptions.HTTPError):
            sync(client, {"start_date": "2020-01-01"}, {}, "credit_notes", {}, {})
        self.assertEqual(sdk_obj.list.call_count, 5)

    @patch("time.sleep", return_value=None)
    def test_sync_retries_on_rate_limit(self, _):
        client = MagicMock()
        sdk_obj = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        http_error = requests.exceptions.HTTPError(response=mock_response)

        sdk_obj.list.side_effect = [
            http_error,
            http_error,
            ([], MagicMock(links={}))
        ]
        setattr(client, STREAM_SDK_OBJECTS["credit_notes"], sdk_obj)
        sync(client, {"start_date": "2020-01-01"}, {}, "credit_notes", {}, {})
        self.assertGreaterEqual(sdk_obj.list.call_count, 3)

    @patch("time.sleep", return_value=None)
    def test_sync_handles_network_error_and_calls_handler(self, _):
        client = MagicMock()
        sdk_obj = MagicMock()
        sdk_obj.client = client

        # Simulate ConnectTimeout exception
        sdk_obj.list.side_effect = requests.exceptions.ConnectTimeout()

        setattr(client, STREAM_SDK_OBJECTS["credit_notes"], sdk_obj)

        with self.assertRaises(requests.exceptions.ConnectTimeout):
            sync(client, {"start_date": "2020-01-01"}, {}, "credit_notes", {}, {})

        self.assertEqual(client.handle_network_error.call_count, 5)
