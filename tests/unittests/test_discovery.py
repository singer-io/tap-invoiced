"""Unit tests for tap_invoiced.discover module.

Covers: discover_streams(), load_schemas(), get_metadata(), field inclusion rules,
and stream access-checking logic (check_stream_access / _check_stream_access).
"""
import unittest
from unittest.mock import patch, MagicMock, call

from singer import metadata
from invoiced.errors import ApiError

from tap_invoiced.discover import (
    discover_streams,
    load_schemas,
    get_metadata,
    _check_stream_access,
    _InvoicedAuthError,
    STREAM_SDK_OBJECTS,
)
from tap_invoiced.stream_access import check_stream_access

EXPECTED_STREAMS = {
    "credit_notes",
    "customers",
    "estimates",
    "invoices",
    "plans",
    "subscriptions",
}


class TestDiscoverStreams(unittest.TestCase):
    """discover_streams() returns a well-formed Singer catalog."""

    def test_returns_streams_key(self):
        """discover_streams() result contains the 'streams' key."""
        result = discover_streams()
        self.assertIn("streams", result)

    def test_returns_all_six_streams(self):
        """discover_streams() includes all six expected tap_stream_ids."""
        result = discover_streams()
        stream_ids = {s["tap_stream_id"] for s in result["streams"]}
        self.assertEqual(EXPECTED_STREAMS, stream_ids)

    def test_each_entry_has_required_catalog_keys(self):
        """Every stream entry has stream, tap_stream_id, schema, metadata, key_properties."""
        result = discover_streams()
        required_keys = ("stream", "tap_stream_id", "schema", "metadata", "key_properties")
        for entry in result["streams"]:
            for key in required_keys:
                self.assertIn(key, entry, f"Missing key '{key}' in stream {entry.get('tap_stream_id')}")

    def test_stream_name_matches_tap_stream_id(self):
        """stream and tap_stream_id are equal in every catalog entry."""
        result = discover_streams()
        for entry in result["streams"]:
            self.assertEqual(entry["stream"], entry["tap_stream_id"])

    def test_key_properties_is_id_for_all_streams(self):
        """All streams use ['id'] as their key_properties."""
        result = discover_streams()
        for entry in result["streams"]:
            self.assertEqual(["id"], entry["key_properties"])

    def test_each_schema_has_properties(self):
        """Every stream schema includes a non-empty 'properties' object."""
        result = discover_streams()
        for entry in result["streams"]:
            self.assertIn("properties", entry["schema"])
            self.assertGreater(len(entry["schema"]["properties"]), 0)

    def test_metadata_is_list(self):
        """Metadata for every stream is a list (Singer format)."""
        result = discover_streams()
        for entry in result["streams"]:
            self.assertIsInstance(entry["metadata"], list)

    def test_forced_replication_method_is_incremental(self):
        """All streams are set to INCREMENTAL replication via metadata."""
        result = discover_streams()
        for entry in result["streams"]:
            mdata_map = metadata.to_map(entry["metadata"])
            method = metadata.get(mdata_map, (), "forced-replication-method")
            self.assertEqual("INCREMENTAL", method,
                             f"Stream {entry['tap_stream_id']} not set to INCREMENTAL")

    def test_valid_replication_key_is_updated_at(self):
        """All streams declare 'updated_at' as their valid replication key."""
        result = discover_streams()
        for entry in result["streams"]:
            mdata_map = metadata.to_map(entry["metadata"])
            rep_keys = metadata.get(mdata_map, (), "valid-replication-keys")
            self.assertEqual(["updated_at"], rep_keys,
                             f"Stream {entry['tap_stream_id']} has wrong replication key")

    def test_id_field_inclusion_is_automatic(self):
        """The 'id' field is marked as inclusion=automatic in every stream."""
        result = discover_streams()
        for entry in result["streams"]:
            mdata_map = metadata.to_map(entry["metadata"])
            inclusion = metadata.get(mdata_map, ("properties", "id"), "inclusion")
            self.assertEqual("automatic", inclusion,
                             f"Stream {entry['tap_stream_id']} 'id' not automatic")

    def test_updated_at_field_inclusion_is_automatic(self):
        """The 'updated_at' field is marked as inclusion=automatic in every stream."""
        result = discover_streams()
        for entry in result["streams"]:
            mdata_map = metadata.to_map(entry["metadata"])
            inclusion = metadata.get(mdata_map, ("properties", "updated_at"), "inclusion")
            self.assertEqual("automatic", inclusion,
                             f"Stream {entry['tap_stream_id']} 'updated_at' not automatic")


class TestLoadSchemas(unittest.TestCase):
    """load_schemas() reads all JSON schema files from the schemas directory."""

    def test_returns_all_six_streams(self):
        """load_schemas() returns all six expected stream schema keys."""
        schemas = load_schemas()
        self.assertEqual(EXPECTED_STREAMS, set(schemas.keys()))

    def test_each_schema_is_dict(self):
        """Each loaded schema is a Python dict."""
        schemas = load_schemas()
        for name, schema in schemas.items():
            self.assertIsInstance(schema, dict, f"Schema '{name}' is not a dict")

    def test_each_schema_has_properties(self):
        """Each loaded schema contains a 'properties' key."""
        schemas = load_schemas()
        for name, schema in schemas.items():
            self.assertIn("properties", schema, f"Schema '{name}' missing 'properties'")

    def test_schemas_not_empty(self):
        """load_schemas() returns at least one schema."""
        schemas = load_schemas()
        self.assertGreater(len(schemas), 0)

    def test_invoices_schema_has_id_field(self):
        """invoices schema contains 'id' as expected key property."""
        schemas = load_schemas()
        self.assertIn("id", schemas["invoices"]["properties"])

    def test_customers_schema_has_id_field(self):
        """customers schema contains 'id' as expected key property."""
        schemas = load_schemas()
        self.assertIn("id", schemas["customers"]["properties"])


class TestGetMetadata(unittest.TestCase):
    """get_metadata() writes correct Singer metadata for a given schema."""

    def _make_schema(self):
        return {
            "properties": {
                "id": {"type": ["null", "integer"]},
                "updated_at": {"type": ["null", "integer"]},
                "name": {"type": ["null", "string"]},
                "description": {"type": ["null", "string"]},
            }
        }

    def test_returns_list(self):
        """get_metadata() returns a list of metadata entries."""
        result = get_metadata(self._make_schema(), ["id"], "INCREMENTAL", "updated_at")
        self.assertIsInstance(result, list)

    def test_table_key_properties_written(self):
        """table-key-properties metadata entry is set correctly."""
        mdata = get_metadata(self._make_schema(), ["id"], "INCREMENTAL", "updated_at")
        mdata_map = metadata.to_map(mdata)
        self.assertEqual(["id"], metadata.get(mdata_map, (), "table-key-properties"))

    def test_forced_replication_method_incremental(self):
        """forced-replication-method is set to INCREMENTAL when provided."""
        mdata = get_metadata(self._make_schema(), ["id"], "INCREMENTAL", "updated_at")
        mdata_map = metadata.to_map(mdata)
        self.assertEqual("INCREMENTAL", metadata.get(mdata_map, (), "forced-replication-method"))

    def test_forced_replication_method_full_table(self):
        """forced-replication-method is set to FULL_TABLE when provided."""
        mdata = get_metadata(self._make_schema(), ["id"], "FULL_TABLE", None)
        mdata_map = metadata.to_map(mdata)
        self.assertEqual("FULL_TABLE", metadata.get(mdata_map, (), "forced-replication-method"))

    def test_valid_replication_keys_written_when_provided(self):
        """valid-replication-keys metadata entry is set when a replication_key is given."""
        mdata = get_metadata(self._make_schema(), ["id"], "INCREMENTAL", "updated_at")
        mdata_map = metadata.to_map(mdata)
        self.assertEqual(["updated_at"], metadata.get(mdata_map, (), "valid-replication-keys"))

    def test_no_valid_replication_keys_when_none(self):
        """valid-replication-keys is NOT written when replication_key is None."""
        mdata = get_metadata(self._make_schema(), ["id"], "FULL_TABLE", None)
        mdata_map = metadata.to_map(mdata)
        self.assertIsNone(metadata.get(mdata_map, (), "valid-replication-keys"))

    def test_key_property_marked_automatic(self):
        """Fields listed in key_properties receive inclusion=automatic."""
        mdata = get_metadata(self._make_schema(), ["id"], "INCREMENTAL", "updated_at")
        mdata_map = metadata.to_map(mdata)
        self.assertEqual("automatic", metadata.get(mdata_map, ("properties", "id"), "inclusion"))

    def test_replication_key_marked_automatic(self):
        """The replication_key field receives inclusion=automatic."""
        mdata = get_metadata(self._make_schema(), ["id"], "INCREMENTAL", "updated_at")
        mdata_map = metadata.to_map(mdata)
        self.assertEqual("automatic", metadata.get(mdata_map, ("properties", "updated_at"), "inclusion"))

    def test_non_key_field_marked_available(self):
        """Fields that are not key/replication fields receive inclusion=available."""
        mdata = get_metadata(self._make_schema(), ["id"], "INCREMENTAL", "updated_at")
        mdata_map = metadata.to_map(mdata)
        self.assertEqual("available", metadata.get(mdata_map, ("properties", "name"), "inclusion"))
        self.assertEqual("available", metadata.get(mdata_map, ("properties", "description"), "inclusion"))

    def test_multiple_key_properties_all_marked_automatic(self):
        """All fields in key_properties list receive inclusion=automatic."""
        schema = {
            "properties": {
                "id": {"type": ["null", "integer"]},
                "account_id": {"type": ["null", "integer"]},
                "updated_at": {"type": ["null", "integer"]},
                "name": {"type": ["null", "string"]},
            }
        }
        mdata = get_metadata(schema, ["id", "account_id"], "INCREMENTAL", "updated_at")
        mdata_map = metadata.to_map(mdata)
        self.assertEqual("automatic", metadata.get(mdata_map, ("properties", "id"), "inclusion"))
        self.assertEqual("automatic", metadata.get(mdata_map, ("properties", "account_id"), "inclusion"))

    def test_updated_field_marked_automatic(self):
        """A field named 'updated' also receives inclusion=automatic."""
        schema = {
            "properties": {
                "id": {"type": ["null", "integer"]},
                "updated": {"type": ["null", "integer"]},
                "name": {"type": ["null", "string"]},
            }
        }
        mdata = get_metadata(schema, ["id"], "INCREMENTAL", "updated_at")
        mdata_map = metadata.to_map(mdata)
        self.assertEqual("automatic", metadata.get(mdata_map, ("properties", "updated"), "inclusion"))


# ---------------------------------------------------------------------------
# check_stream_access (shared utils helper)
# ---------------------------------------------------------------------------

class TestCheckStreamAccessHelper(unittest.TestCase):
    """Tests for the reusable check_stream_access helper in tap_invoiced.utils."""

    def test_returns_true_when_probe_succeeds(self):
        result = check_stream_access("invoices", probe_fn=lambda: None, auth_error_types=_InvoicedAuthError)
        self.assertTrue(result)

    def test_returns_false_on_auth_error(self):
        def _raise():
            raise _InvoicedAuthError("403 Forbidden")

        result = check_stream_access("invoices", probe_fn=_raise, auth_error_types=_InvoicedAuthError)
        self.assertFalse(result)

    def test_reraises_non_auth_error_when_fallback_false(self):
        def _raise():
            raise RuntimeError("network error")

        with self.assertRaises(RuntimeError):
            check_stream_access("invoices", probe_fn=_raise, auth_error_types=_InvoicedAuthError,
                                fallback_accessible=False)

    def test_returns_true_on_non_auth_error_when_fallback_true(self):
        def _raise():
            raise RuntimeError("400 Bad Request")

        result = check_stream_access("invoices", probe_fn=_raise, auth_error_types=_InvoicedAuthError,
                                     fallback_accessible=True)
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# _check_stream_access (tap-invoiced-specific wrapper)
# ---------------------------------------------------------------------------

class TestInvoicedCheckStreamAccess(unittest.TestCase):
    """Tests for the _check_stream_access wrapper in tap_invoiced.discover."""

    def _make_client(self, side_effect=None):
        client = MagicMock()
        sdk_obj = MagicMock()
        if side_effect:
            sdk_obj.list.side_effect = side_effect
        # Make getattr(client, sdk_attr) return the mock sdk_obj
        for attr in STREAM_SDK_OBJECTS.values():
            setattr(client, attr, sdk_obj)
        return client, sdk_obj

    def test_returns_true_when_accessible(self):
        client, sdk_obj = self._make_client()
        result = _check_stream_access(client, "invoices")
        self.assertTrue(result)
        sdk_obj.list.assert_called_once_with(per_page=1, page=1)

    def test_returns_false_on_403_api_error(self):
        exc = ApiError()
        exc.http_status = 403
        client, _ = self._make_client(side_effect=exc)
        result = _check_stream_access(client, "customers")
        self.assertFalse(result)

    def test_returns_false_on_401_api_error(self):
        exc = ApiError()
        exc.http_status = 401
        client, _ = self._make_client(side_effect=exc)
        result = _check_stream_access(client, "invoices")
        self.assertFalse(result)

    def test_reraises_non_auth_api_error(self):
        exc = ApiError()
        exc.http_status = 500
        client, _ = self._make_client(side_effect=exc)
        with self.assertRaises(ApiError):
            _check_stream_access(client, "invoices")

    def test_unknown_stream_returns_true(self):
        client, sdk_obj = self._make_client()
        result = _check_stream_access(client, "unknown_stream")
        self.assertTrue(result)
        sdk_obj.list.assert_not_called()


# ---------------------------------------------------------------------------
# discover_streams() with client (access-gated discovery)
# ---------------------------------------------------------------------------

class TestDiscoverStreamsWithClient(unittest.TestCase):
    """Tests for discover_streams() when a client is supplied."""

    @patch("tap_invoiced.discover._check_stream_access")
    def test_all_accessible_all_in_catalog(self, mock_check):
        """All streams accessible → all six appear in the catalog."""
        mock_check.return_value = True
        client = MagicMock()
        result = discover_streams(client)
        stream_ids = {s["tap_stream_id"] for s in result["streams"]}
        self.assertEqual(EXPECTED_STREAMS, stream_ids)

    @patch("tap_invoiced.discover._check_stream_access")
    def test_inaccessible_stream_excluded(self, mock_check):
        """A stream returning False from access check is excluded from the catalog."""
        blocked = "invoices"
        mock_check.side_effect = lambda client, name: name != blocked
        client = MagicMock()
        result = discover_streams(client)
        stream_ids = {s["tap_stream_id"] for s in result["streams"]}
        self.assertNotIn(blocked, stream_ids)
        self.assertEqual(EXPECTED_STREAMS - {blocked}, stream_ids)

    @patch("tap_invoiced.discover._check_stream_access")
    def test_all_inaccessible_returns_empty_catalog(self, mock_check):
        """All streams inaccessible → empty streams list."""
        mock_check.return_value = False
        client = MagicMock()
        result = discover_streams(client)
        self.assertEqual([], result["streams"])

    @patch("tap_invoiced.discover._check_stream_access")
    def test_check_called_once_per_stream(self, mock_check):
        """_check_stream_access is called exactly once per stream."""
        mock_check.return_value = True
        client = MagicMock()
        discover_streams(client)
        self.assertEqual(len(EXPECTED_STREAMS), mock_check.call_count)

    def test_no_client_skips_access_check(self):
        """discover_streams(None) skips access checks and returns all streams."""
        result = discover_streams(None)
        stream_ids = {s["tap_stream_id"] for s in result["streams"]}
        self.assertEqual(EXPECTED_STREAMS, stream_ids)

    def test_no_client_default_arg_skips_access_check(self):
        """discover_streams() with no argument skips access checks."""
        result = discover_streams()
        stream_ids = {s["tap_stream_id"] for s in result["streams"]}
        self.assertEqual(EXPECTED_STREAMS, stream_ids)


if __name__ == "__main__":
    unittest.main()
