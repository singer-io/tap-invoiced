"""Test that with no fields selected, automatic fields are still replicated."""
from base import TapInvoicedBaseTest
from tap_tester.base_suite_tests.automatic_fields_test import MinimumSelectionTest


class TapInvoicedAutomaticFields(MinimumSelectionTest, TapInvoicedBaseTest):
    """Test that with no fields selected for a stream, automatic fields are still
    replicated.

    Automatic fields for tap-invoiced:
      - All streams: id (key_property), updated_at (replication_key)
    """

    @staticmethod
    def name():
        return "tap_tester_tap_invoiced_automatic_fields_test"

    def streams_to_test(self):
        # Exclude streams with known missing test data in the test environment.
        streams_to_exclude = set()
        return self.expected_stream_names().difference(streams_to_exclude)
