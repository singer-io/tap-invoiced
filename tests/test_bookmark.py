"""Test that tap sets bookmarks and respects them on subsequent syncs."""
from base import TapInvoicedBaseTest
from tap_tester.base_suite_tests.bookmark_test import BookmarkTest


class TapInvoicedBookMarkTest(BookmarkTest, TapInvoicedBaseTest):
    """Test tap sets a bookmark and respects it for the next sync of a stream."""

    # All timestamps are Unix epoch integers in the Invoiced API.
    # tap_tester BookmarkTest expects string format; the tap stores integers
    # natively so we note the format here for documentation purposes.
    bookmark_format = "%Y-%m-%dT%H:%M:%S.%fZ"

    initial_bookmarks = {
        "bookmarks": {
            # All six streams are INCREMENTAL on updated_at (Unix epoch integer).
            # These serve as the "already synced up to this point" seed state.
            "customers":     {"updated_at": "2020-01-01T00:00:00Z"},
        }
    }

    @staticmethod
    def name():
        return "tap_tester_tap_invoiced_bookmark_test"

    def streams_to_test(self):
        # The following streams are excluded because all their test data was
        # created in the same narrow time window
        streams_to_exclude = {
            "invoices",
            "plans",
            "subscriptions",
            "estimates",
            "credit_notes",
        }
        return self.expected_stream_names().difference(streams_to_exclude)
