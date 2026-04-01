"""Test that running the tap with all fields selected replicates every schema field."""
from base import TapInvoicedBaseTest
from tap_tester.base_suite_tests.all_fields_test import AllFieldsTest

# Fields that exist in the schema but may not be returned by the test-account API.
# Populate after a first live test run reveals gaps.  Leave empty until then.
# Example format:
#   "invoices": {"subscription_terms"},  # only set when subscription billing is enabled
KNOWN_MISSING_FIELDS = {
    # "<stream_name>": {"<field_name>"},
}


class TapInvoicedAllFields(AllFieldsTest, TapInvoicedBaseTest):
    """Ensure running the tap with all streams and fields selected results in
    the replication of all fields present in the JSON schemas."""

    MISSING_FIELDS = KNOWN_MISSING_FIELDS

    @staticmethod
    def name():
        return "tap_tester_tap_invoiced_all_fields_test"

    def streams_to_test(self):
        # Exclude streams with no data in the test environment.
        streams_to_exclude = set()
        return self.expected_stream_names().difference(streams_to_exclude)
