"""Unit tests for tap_invoiced.sync module.

Covers: get_selected_streams(), fetch_with_backoff_retry(), sync_streams(), sync().
All HTTP/SDK calls are mocked — no real network traffic.
"""
import unittest
from unittest.mock import patch, MagicMock, call

from singer import metadata

from tap_invoiced.sync import (
    sync_streams,
    get_selected_streams,
    sync,
    fetch_with_backoff_retry,
)


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


def _make_stream_mock(stream_id, selected=True):
    """Build a mock Singer catalog stream entry with real Singer metadata."""
    mdata = metadata.new()
    mdata = metadata.write(mdata, (), "selected", selected)
    metadata_list = metadata.to_list(mdata)

    stream = MagicMock()
    stream.tap_stream_id = stream_id
    stream.metadata = metadata_list
    stream.key_properties = ["id"]
    stream.schema.to_dict.return_value = _test_schema()
    return stream


def _test_schema():
    return {
        "properties": {
            "id":         {"type": ["null", "integer"]},
            "created_at": {"type": ["null", "integer"]},
            "updated_at": {"type": ["null", "integer"]},
            "name":       {"type": ["null", "string"]},
        }
    }


def _test_stream_metadata():
    """Build a to_map metadata dict with all test fields marked automatic."""
    mdata = metadata.new()
    mdata = metadata.write(mdata, (), "selected", True)
    for field in ["id", "created_at", "updated_at", "name"]:
        mdata = metadata.write(mdata, ("properties", field), "inclusion", "automatic")
    return metadata.to_map(metadata.to_list(mdata))


class MockSDKObject:
    """Mimics an Invoiced SDK record.  dict(obj) and obj.get() both work."""

    def __init__(self, data):
        self._data = data

    def __iter__(self):
        return iter(self._data.items())

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getitem__(self, key):
        return self._data[key]


def _make_list_response(records, has_next=False):
    """Return (objects, list_metadata) as the Invoiced SDK returns."""
    list_meta = MagicMock()
    list_meta.links = {"next": "https://api.invoiced.com/next"} if has_next else {}
    return records, list_meta


# ---------------------------------------------------------------------------
# TestGetSelectedStreams
# ---------------------------------------------------------------------------

class TestGetSelectedStreams(unittest.TestCase):
    """get_selected_streams() filters the catalog to selected streams only."""

    def test_selected_stream_included(self):
        """A stream with selected=True is included in the result."""
        catalog = MagicMock()
        catalog.streams = [_make_stream_mock("customers", selected=True)]
        result = get_selected_streams(catalog)
        self.assertIn("customers", result)

    def test_unselected_stream_excluded(self):
        """A stream with selected=False is not included in the result."""
        catalog = MagicMock()
        catalog.streams = [_make_stream_mock("customers", selected=False)]
        result = get_selected_streams(catalog)
        self.assertNotIn("customers", result)

    def test_empty_catalog_returns_empty_list(self):
        """An empty catalog produces an empty selected-streams list."""
        catalog = MagicMock()
        catalog.streams = []
        result = get_selected_streams(catalog)
        self.assertEqual([], result)

    def test_only_selected_streams_returned_from_mixed_catalog(self):
        """Only selected streams are returned when the catalog has mixed selection."""
        catalog = MagicMock()
        catalog.streams = [
            _make_stream_mock("customers", selected=True),
            _make_stream_mock("invoices",  selected=False),
            _make_stream_mock("plans",     selected=True),
        ]
        result = get_selected_streams(catalog)
        self.assertIn("customers", result)
        self.assertNotIn("invoices", result)
        self.assertIn("plans", result)

    def test_all_six_streams_can_be_selected(self):
        """All six streams are returned when every stream is selected."""
        streams = [
            "credit_notes", "customers", "estimates",
            "invoices", "plans", "subscriptions",
        ]
        catalog = MagicMock()
        catalog.streams = [_make_stream_mock(s, selected=True) for s in streams]
        result = get_selected_streams(catalog)
        self.assertEqual(set(streams), set(result))

    def test_result_is_a_list(self):
        """get_selected_streams() always returns a list (not a set or generator)."""
        catalog = MagicMock()
        catalog.streams = [_make_stream_mock("customers", selected=True)]
        result = get_selected_streams(catalog)
        self.assertIsInstance(result, list)


# ---------------------------------------------------------------------------
# TestFetchWithBackoffRetry
# ---------------------------------------------------------------------------

class TestFetchWithBackoffRetry(unittest.TestCase):
    """fetch_with_backoff_retry() delegates to sdkObject.list() with correct args."""

    def test_calls_list_with_correct_positional_and_keyword_args(self):
        """sdkObject.list() is called with expected per_page, page, include, sort, updated_after."""
        sdk_obj = MagicMock()
        sdk_obj.list.return_value = ([], MagicMock(links={}))
        fetch_with_backoff_retry(sdk_obj, 1, 1577836800)
        sdk_obj.list.assert_called_once_with(
            per_page=100,
            page=1,
            include="updated_at",
            sort="updated_at ASC",
            updated_after=1577836800,
        )

    def test_returns_objects_and_metadata_tuple(self):
        """fetch_with_backoff_retry() returns the (objects, list_metadata) tuple."""
        sdk_obj = MagicMock()
        record = MockSDKObject({"id": 1, "created_at": 0, "updated_at": 0})
        list_meta = MagicMock(links={})
        sdk_obj.list.return_value = ([record], list_meta)

        objects, meta = fetch_with_backoff_retry(sdk_obj, 1, 0)
        self.assertEqual(1, len(objects))
        self.assertIs(list_meta, meta)

    def test_empty_page_returns_empty_list(self):
        """fetch_with_backoff_retry() can return an empty records list."""
        sdk_obj = MagicMock()
        sdk_obj.list.return_value = ([], MagicMock(links={}))
        objects, _ = fetch_with_backoff_retry(sdk_obj, 2, 0)
        self.assertEqual([], objects)

    def test_page_number_forwarded_to_sdk(self):
        """The page argument is passed through to sdkObject.list()."""
        sdk_obj = MagicMock()
        sdk_obj.list.return_value = ([], MagicMock(links={}))
        fetch_with_backoff_retry(sdk_obj, 5, 0)
        self.assertEqual(5, sdk_obj.list.call_args[1]["page"])


# ---------------------------------------------------------------------------
# TestSyncStreams
# ---------------------------------------------------------------------------

class TestSyncStreams(unittest.TestCase):
    """sync_streams() orchestrates client creation, schema writing, and per-stream sync."""

    @patch("tap_invoiced.sync.sync")
    @patch("tap_invoiced.sync.singer.write_schema")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_builds_invoiced_client_with_api_key(
        self, mock_client_cls, mock_write_schema, mock_sync
    ):
        """invoiced.Client is constructed with the api_key from config."""
        catalog = MagicMock()
        catalog.streams = [_make_stream_mock("customers", selected=True)]
        sync_streams(_make_config(), {}, catalog)
        mock_client_cls.assert_called_once_with("test_api_key", False)

    @patch("tap_invoiced.sync.sync")
    @patch("tap_invoiced.sync.singer.write_schema")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_builds_invoiced_client_with_sandbox_true(
        self, mock_client_cls, mock_write_schema, mock_sync
    ):
        """invoiced.Client is constructed with sandbox=True when config sandbox='true'."""
        catalog = MagicMock()
        catalog.streams = [_make_stream_mock("customers", selected=True)]
        sync_streams(_make_config(sandbox="true"), {}, catalog)
        mock_client_cls.assert_called_once_with("test_api_key", True)

    @patch("tap_invoiced.sync.sync")
    @patch("tap_invoiced.sync.singer.write_schema")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_sandbox_false_when_config_value_is_not_true_string(
        self, mock_client_cls, mock_write_schema, mock_sync
    ):
        """invoiced.Client uses sandbox=False when config sandbox is absent or not 'true'."""
        catalog = MagicMock()
        catalog.streams = [_make_stream_mock("customers", selected=True)]
        sync_streams(_make_config(sandbox="false"), {}, catalog)
        mock_client_cls.assert_called_once_with("test_api_key", False)

    @patch("tap_invoiced.sync.sync")
    @patch("tap_invoiced.sync.singer.write_schema")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_writes_schema_for_selected_stream(
        self, mock_client_cls, mock_write_schema, mock_sync
    ):
        """write_schema is called once for a selected stream with correct stream_id."""
        catalog = MagicMock()
        catalog.streams = [_make_stream_mock("customers", selected=True)]
        sync_streams(_make_config(), {}, catalog)
        mock_write_schema.assert_called_once()
        self.assertEqual("customers", mock_write_schema.call_args[0][0])

    @patch("tap_invoiced.sync.sync")
    @patch("tap_invoiced.sync.singer.write_schema")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_skips_schema_write_for_unselected_stream(
        self, mock_client_cls, mock_write_schema, mock_sync
    ):
        """write_schema and sync are NOT called for unselected streams."""
        catalog = MagicMock()
        catalog.streams = [_make_stream_mock("customers", selected=False)]
        sync_streams(_make_config(), {}, catalog)
        mock_write_schema.assert_not_called()
        mock_sync.assert_not_called()

    @patch("tap_invoiced.sync.sync")
    @patch("tap_invoiced.sync.singer.write_schema")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_sync_called_once_per_selected_stream(
        self, mock_client_cls, mock_write_schema, mock_sync
    ):
        """sync() is called exactly once per selected stream."""
        catalog = MagicMock()
        catalog.streams = [
            _make_stream_mock("customers", selected=True),
            _make_stream_mock("invoices",  selected=True),
            _make_stream_mock("plans",     selected=False),
        ]
        sync_streams(_make_config(), {}, catalog)
        self.assertEqual(2, mock_sync.call_count)

    @patch("tap_invoiced.sync.sync")
    @patch("tap_invoiced.sync.singer.write_schema")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_empty_catalog_performs_no_sync(
        self, mock_client_cls, mock_write_schema, mock_sync
    ):
        """No writes occur when the catalog has no selected streams."""
        catalog = MagicMock()
        catalog.streams = []
        sync_streams(_make_config(), {}, catalog)
        mock_write_schema.assert_not_called()
        mock_sync.assert_not_called()


# ---------------------------------------------------------------------------
# TestSync
# ---------------------------------------------------------------------------

class TestSync(unittest.TestCase):
    """sync() pages through records and correctly manages bookmarks and state."""

    @patch("tap_invoiced.sync.singer.write_state")
    @patch("tap_invoiced.sync.singer.write_bookmark")
    @patch("tap_invoiced.sync.singer.write_record")
    @patch("tap_invoiced.sync.singer.get_bookmark")
    @patch("tap_invoiced.sync.fetch_with_backoff_retry")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_reads_bookmark_from_state(
        self, mock_client_cls, mock_fetch, mock_get_bm,
        mock_write_rec, mock_write_bm, mock_write_state
    ):
        """sync() calls singer.get_bookmark with the correct stream and key."""
        mock_get_bm.return_value = 1609459200
        mock_fetch.return_value = _make_list_response([], has_next=False)

        sync(mock_client_cls.return_value, _make_config(), {},
             "customers", _test_schema(), _test_stream_metadata())

        mock_get_bm.assert_called_once_with({}, "customers", "updated_at")

    @patch("tap_invoiced.sync.singer.write_state")
    @patch("tap_invoiced.sync.singer.write_bookmark")
    @patch("tap_invoiced.sync.singer.write_record")
    @patch("tap_invoiced.sync.singer.get_bookmark")
    @patch("tap_invoiced.sync.fetch_with_backoff_retry")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_falls_back_to_start_date_as_integer_when_no_bookmark(
        self, mock_client_cls, mock_fetch, mock_get_bm,
        mock_write_rec, mock_write_bm, mock_write_state
    ):
        """sync() converts start_date to an integer epoch when no bookmark exists."""
        mock_get_bm.return_value = None
        mock_fetch.return_value = _make_list_response([], has_next=False)

        sync(mock_client_cls.return_value, _make_config(start_date="2020-01-01T00:00:00Z"),
             {}, "customers", _test_schema(), _test_stream_metadata())

        # Positional args to fetch_with_backoff_retry: (sdkObject, page, bookmark)
        bookmark_used = mock_fetch.call_args[0][2]
        self.assertIsInstance(bookmark_used, (int, float))

    @patch("tap_invoiced.sync.singer.write_state")
    @patch("tap_invoiced.sync.singer.write_bookmark")
    @patch("tap_invoiced.sync.singer.write_record")
    @patch("tap_invoiced.sync.singer.get_bookmark")
    @patch("tap_invoiced.sync.fetch_with_backoff_retry")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_write_record_called_once_per_object(
        self, mock_client_cls, mock_fetch, mock_get_bm,
        mock_write_rec, mock_write_bm, mock_write_state
    ):
        """singer.write_record is called exactly once for each API record."""
        mock_get_bm.return_value = 1
        records = [
            MockSDKObject({"id": 1, "created_at": 1000, "updated_at": 1000, "name": "Alice"}),
            MockSDKObject({"id": 2, "created_at": 2000, "updated_at": 2000, "name": "Bob"}),
        ]
        mock_fetch.return_value = _make_list_response(records, has_next=False)

        sync(mock_client_cls.return_value, _make_config(), {},
             "customers", _test_schema(), _test_stream_metadata())

        self.assertEqual(2, mock_write_rec.call_count)

    @patch("tap_invoiced.sync.singer.write_state")
    @patch("tap_invoiced.sync.singer.write_bookmark")
    @patch("tap_invoiced.sync.singer.write_record")
    @patch("tap_invoiced.sync.singer.get_bookmark")
    @patch("tap_invoiced.sync.fetch_with_backoff_retry")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_no_write_record_when_api_returns_empty_page(
        self, mock_client_cls, mock_fetch, mock_get_bm,
        mock_write_rec, mock_write_bm, mock_write_state
    ):
        """singer.write_record is never called when the API returns zero records."""
        mock_get_bm.return_value = None
        mock_fetch.return_value = _make_list_response([], has_next=False)

        sync(mock_client_cls.return_value, _make_config(), {},
             "customers", _test_schema(), _test_stream_metadata())

        mock_write_rec.assert_not_called()

    @patch("tap_invoiced.sync.singer.write_state")
    @patch("tap_invoiced.sync.singer.write_bookmark")
    @patch("tap_invoiced.sync.singer.write_record")
    @patch("tap_invoiced.sync.singer.get_bookmark")
    @patch("tap_invoiced.sync.fetch_with_backoff_retry")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_paginates_across_multiple_pages(
        self, mock_client_cls, mock_fetch, mock_get_bm,
        mock_write_rec, mock_write_bm, mock_write_state
    ):
        """sync() requests subsequent pages while the API signals more data."""
        mock_get_bm.return_value = 1
        page1 = [MockSDKObject({"id": 1, "created_at": 1000, "updated_at": 1000, "name": "A"})]
        page2 = [MockSDKObject({"id": 2, "created_at": 2000, "updated_at": 2000, "name": "B"})]
        mock_fetch.side_effect = [
            _make_list_response(page1, has_next=True),
            _make_list_response(page2, has_next=False),
        ]

        sync(mock_client_cls.return_value, _make_config(), {},
             "customers", _test_schema(), _test_stream_metadata())

        self.assertEqual(2, mock_fetch.call_count)
        self.assertEqual(2, mock_write_rec.call_count)

    @patch("tap_invoiced.sync.singer.write_state")
    @patch("tap_invoiced.sync.singer.write_bookmark")
    @patch("tap_invoiced.sync.singer.write_record")
    @patch("tap_invoiced.sync.singer.get_bookmark")
    @patch("tap_invoiced.sync.fetch_with_backoff_retry")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_stops_pagination_when_no_next_link(
        self, mock_client_cls, mock_fetch, mock_get_bm,
        mock_write_rec, mock_write_bm, mock_write_state
    ):
        """sync() makes exactly one fetch call when the first page has no 'next' link."""
        mock_get_bm.return_value = None
        mock_fetch.return_value = _make_list_response([], has_next=False)

        sync(mock_client_cls.return_value, _make_config(), {},
             "customers", _test_schema(), _test_stream_metadata())

        self.assertEqual(1, mock_fetch.call_count)

    @patch("tap_invoiced.sync.singer.write_state")
    @patch("tap_invoiced.sync.singer.write_bookmark")
    @patch("tap_invoiced.sync.singer.write_record")
    @patch("tap_invoiced.sync.singer.get_bookmark")
    @patch("tap_invoiced.sync.fetch_with_backoff_retry")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_bookmark_updated_to_max_updated_at(
        self, mock_client_cls, mock_fetch, mock_get_bm,
        mock_write_rec, mock_write_bm, mock_write_state
    ):
        """singer.write_bookmark is called with the highest updated_at across all records."""
        mock_get_bm.return_value = 1000
        records = [
            MockSDKObject({"id": 1, "created_at": 500, "updated_at": 3000, "name": "A"}),
            MockSDKObject({"id": 2, "created_at": 500, "updated_at": 2000, "name": "B"}),
        ]
        mock_fetch.return_value = _make_list_response(records, has_next=False)

        sync(mock_client_cls.return_value, _make_config(), {},
             "customers", _test_schema(), _test_stream_metadata())

        bookmark_values = [c[0][3] for c in mock_write_bm.call_args_list]
        self.assertIn("1970-01-01T00:50:00.000000Z", bookmark_values)

    @patch("tap_invoiced.sync.singer.write_state")
    @patch("tap_invoiced.sync.singer.write_bookmark")
    @patch("tap_invoiced.sync.singer.write_record")
    @patch("tap_invoiced.sync.singer.get_bookmark")
    @patch("tap_invoiced.sync.fetch_with_backoff_retry")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_bookmark_not_updated_for_older_records(
        self, mock_client_cls, mock_fetch, mock_get_bm,
        mock_write_rec, mock_write_bm, mock_write_state
    ):
        """singer.write_bookmark is NOT called when all records are older than the bookmark."""
        mock_get_bm.return_value = 9999999
        records = [
            MockSDKObject({"id": 1, "created_at": 500, "updated_at": 1000, "name": "A"}),
        ]
        mock_fetch.return_value = _make_list_response(records, has_next=False)

        sync(mock_client_cls.return_value, _make_config(), {},
             "customers", _test_schema(), _test_stream_metadata())

        mock_write_bm.assert_not_called()

    @patch("tap_invoiced.sync.singer.write_state")
    @patch("tap_invoiced.sync.singer.write_bookmark")
    @patch("tap_invoiced.sync.singer.write_record")
    @patch("tap_invoiced.sync.singer.get_bookmark")
    @patch("tap_invoiced.sync.fetch_with_backoff_retry")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_write_state_called_once_per_page(
        self, mock_client_cls, mock_fetch, mock_get_bm,
        mock_write_rec, mock_write_bm, mock_write_state
    ):
        """singer.write_state is emitted exactly once per fetched page."""
        mock_get_bm.return_value = None
        mock_fetch.side_effect = [
            _make_list_response([], has_next=True),
            _make_list_response([], has_next=False),
        ]

        sync(mock_client_cls.return_value, _make_config(), {},
             "customers", _test_schema(), _test_stream_metadata())

        self.assertEqual(2, mock_write_state.call_count)

    @patch("tap_invoiced.sync.singer.write_state")
    @patch("tap_invoiced.sync.singer.write_bookmark")
    @patch("tap_invoiced.sync.singer.write_record")
    @patch("tap_invoiced.sync.singer.get_bookmark")
    @patch("tap_invoiced.sync.fetch_with_backoff_retry")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_negative_created_at_clamped_to_zero(
        self, mock_client_cls, mock_fetch, mock_get_bm,
        mock_write_rec, mock_write_bm, mock_write_state
    ):
        """A negative created_at value is clamped to 0 before being emitted."""
        mock_get_bm.return_value = 1
        records = [
            MockSDKObject({"id": 1, "created_at": -500, "updated_at": 1000, "name": "X"}),
        ]
        mock_fetch.return_value = _make_list_response(records, has_next=False)

        sync(mock_client_cls.return_value, _make_config(), {},
             "customers", _test_schema(), _test_stream_metadata())

        mock_write_rec.assert_called_once()
        written_record = mock_write_rec.call_args[0][1]
        self.assertEqual(0, written_record["created_at"])

    @patch("tap_invoiced.sync.singer.write_state")
    @patch("tap_invoiced.sync.singer.write_bookmark")
    @patch("tap_invoiced.sync.singer.write_record")
    @patch("tap_invoiced.sync.singer.get_bookmark")
    @patch("tap_invoiced.sync.fetch_with_backoff_retry")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_negative_updated_at_clamped_to_zero(
        self, mock_client_cls, mock_fetch, mock_get_bm,
        mock_write_rec, mock_write_bm, mock_write_state
    ):
        """A negative updated_at value is clamped to 0 before being emitted."""
        mock_get_bm.return_value = -1000
        records = [
            MockSDKObject({"id": 1, "created_at": 1000, "updated_at": -100, "name": "Y"}),
        ]
        mock_fetch.return_value = _make_list_response(records, has_next=False)

        sync(mock_client_cls.return_value, _make_config(), {},
             "customers", _test_schema(), _test_stream_metadata())

        mock_write_rec.assert_called_once()
        written_record = mock_write_rec.call_args[0][1]
        self.assertEqual(0, written_record["updated_at"])

    @patch("tap_invoiced.sync.singer.write_state")
    @patch("tap_invoiced.sync.singer.write_bookmark")
    @patch("tap_invoiced.sync.singer.write_record")
    @patch("tap_invoiced.sync.singer.get_bookmark")
    @patch("tap_invoiced.sync.fetch_with_backoff_retry")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_write_record_stream_name_correct(
        self, mock_client_cls, mock_fetch, mock_get_bm,
        mock_write_rec, mock_write_bm, mock_write_state
    ):
        """singer.write_record is called with the correct stream name."""
        mock_get_bm.return_value = 1
        records = [MockSDKObject({"id": 99, "created_at": 1, "updated_at": 1, "name": "Z"})]
        mock_fetch.return_value = _make_list_response(records, has_next=False)

        sync(mock_client_cls.return_value, _make_config(), {},
             "invoices", _test_schema(), _test_stream_metadata())

        self.assertEqual("invoices", mock_write_rec.call_args[0][0])

    @patch("tap_invoiced.sync.singer.write_state")
    @patch("tap_invoiced.sync.singer.write_bookmark")
    @patch("tap_invoiced.sync.singer.write_record")
    @patch("tap_invoiced.sync.singer.get_bookmark")
    @patch("tap_invoiced.sync.fetch_with_backoff_retry")
    @patch("tap_invoiced.sync.invoiced.Client")
    def test_first_page_requested_with_page_number_one(
        self, mock_client_cls, mock_fetch, mock_get_bm,
        mock_write_rec, mock_write_bm, mock_write_state
    ):
        """The first call to fetch_with_backoff_retry uses page=1."""
        mock_get_bm.return_value = None
        mock_fetch.return_value = _make_list_response([], has_next=False)

        sync(mock_client_cls.return_value, _make_config(), {},
             "customers", _test_schema(), _test_stream_metadata())

        # Positional args: (sdkObject, page, bookmark) — page is index 1
        page_used = mock_fetch.call_args[0][1]
        self.assertEqual(1, page_used)


if __name__ == "__main__":
    unittest.main()
