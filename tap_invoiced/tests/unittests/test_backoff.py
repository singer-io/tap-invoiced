import unittest
from unittest.mock import patch, MagicMock
import requests

from tap_invoiced.sync import sync, STREAM_SDK_OBJECTS


class TestSyncBackoff(unittest.TestCase):

    @patch("time.sleep", return_value=None)  # speeds up backoff wait
    def test_sync_retries_on_server_error(self, _):
        """
        Test that sync retries on HTTPError and eventually succeeds.
        """
        client = MagicMock()
        sdk_obj = MagicMock()
        sdk_obj.list.side_effect = [
            requests.exceptions.HTTPError("Server error 1"),
            requests.exceptions.HTTPError("Server error 1"),
            requests.exceptions.HTTPError("Server error 1"),
            requests.exceptions.HTTPError("Server error 1"),
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

