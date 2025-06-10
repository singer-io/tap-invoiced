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
        client_mock = MagicMock()
        config = {"start_date": "2020-01-01"}
        state = {}
        stream_name = "credit_notes"
        schema = {}
        stream_metadata = {}

        sdk_object_mock = MagicMock()
        sdk_object_mock.list.side_effect = [
            requests.exceptions.HTTPError("Server error 1"),
            requests.exceptions.HTTPError("Server error 1"),
            requests.exceptions.HTTPError("Server error 1"),
            requests.exceptions.HTTPError("Server error 1"),
            ([], MagicMock(links={})),  # success on 5th call
        ]

        setattr(client_mock, STREAM_SDK_OBJECTS[stream_name], sdk_object_mock)

        sync(client_mock, config, state, stream_name, schema, stream_metadata)

        self.assertGreaterEqual(sdk_object_mock.list.call_count, 5)

    @patch("time.sleep", return_value=None)  # speeds up test by skipping sleep
    def test_make_request_eventually_succeeds_after_retry(self, _):
        """
        Test that sync retries a few times then succeeds.
        """
        client_mock = MagicMock()
        config = {"start_date": "2020-01-01"}
        state = {}
        stream_name = "credit_notes"
        schema = {}
        stream_metadata = {}

        sdk_object_mock = MagicMock()
        sdk_object_mock.list.side_effect = [
            requests.exceptions.HTTPError("Temporary 500 error"),
            requests.exceptions.HTTPError("Temporary 500 error"),
            ([], MagicMock(links={}))  # success on third attempt
        ]

        setattr(client_mock, STREAM_SDK_OBJECTS[stream_name], sdk_object_mock)

        sync(client_mock, config, state, stream_name, schema, stream_metadata)

        self.assertEqual(sdk_object_mock.list.call_count, 3)

    @patch("time.sleep", return_value=None)  # skip delays from backoff
    def test_make_request_raises_runtime_error_for_other_errors(self, _):
        """
        Test that RuntimeError is not retried and fails immediately.
        """
        client_mock = MagicMock()
        config = {"start_date": "2020-01-01"}
        state = {}
        stream_name = "credit_notes"
        schema = {}
        stream_metadata = {}

        sdk_object_mock = MagicMock()
        sdk_object_mock.list.side_effect = RuntimeError("Unexpected error")

        setattr(client_mock, STREAM_SDK_OBJECTS[stream_name], sdk_object_mock)

        with self.assertRaises(RuntimeError):
            sync(client_mock, config, state, stream_name, schema, stream_metadata)

        self.assertEqual(sdk_object_mock.list.call_count, 1)



    @patch("time.sleep", return_value=None)
    def test_sync_raises_after_max_retries(self, _):
        """
        Test that sync raises HTTPError after max retries are exceeded.
        """
        client_mock = MagicMock()
        config = {"start_date": "2020-01-01"}
        state = {}
        stream_name = "credit_notes"
        schema = {}
        stream_metadata = {}

        sdk_object_mock = MagicMock()
        # Simulate HTTPError for all attempts (max_tries=5)
        sdk_object_mock.list.side_effect = [requests.exceptions.HTTPError("Persistent error")] * 5

        setattr(client_mock, STREAM_SDK_OBJECTS[stream_name], sdk_object_mock)

        with self.assertRaises(requests.exceptions.HTTPError):
            sync(client_mock, config, state, stream_name, schema, stream_metadata)

        self.assertEqual(sdk_object_mock.list.call_count, 5)
