"""Test that tap can replicate multiple pages of data for paginated streams."""
from tap_tester.base_suite_tests.pagination_test import PaginationTest
from base import TapInvoicedBaseTest


class TapInvoicedPaginationTest(PaginationTest, TapInvoicedBaseTest):
    """Ensure tap can replicate multiple pages of data for streams that use pagination.

    The Invoiced API paginates via `per_page=100` and a `next` link in list metadata.
    Each stream uses page size 100 (API_LIMIT=100 in base.py).
    Streams whose test-account record count is unlikely to exceed 100 should be
    added to streams_to_exclude below.
    """

    @staticmethod
    def name():
        return "tap_tester_tap_invoiced_pagination_test"

    def streams_to_test(self):
        # Exclude streams that typically have fewer than 100 records in a test account.
        # plans is a reference/lookup table — likely < 100 records in sandbox.
        streams_to_exclude = {
            "plans",  # reference / catalog stream; sandbox typically has < 100 records
        }
        return self.expected_stream_names().difference(streams_to_exclude)
