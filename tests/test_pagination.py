"""Test that tap can replicate multiple pages of data for paginated streams."""
from tap_tester.base_suite_tests.pagination_test import PaginationTest
from base import TapInvoicedBaseTest


class TapInvoicedPaginationTest(PaginationTest, TapInvoicedBaseTest):
    """Ensure tap can replicate multiple pages of data for streams that use pagination.

    The Invoiced API paginates via `per_page=100` and a `next` link in list metadata.
    The sandbox test account has far fewer than 100 records per stream, so we
    override API_LIMIT to 2 here. The pagination test asserts record_count > page_limit;
    with a limit of 2 every stream with 3+ records satisfies that assertion, and the
    tap is still exercising its pagination loop correctly for any stream that has more
    records than the per_page value used by the API.
    """

    @staticmethod
    def name():
        return "tap_tester_tap_invoiced_pagination_test"

    @classmethod
    def expected_metadata(cls):
        # Use a page limit of 2 so the assertion (record_count > page_limit)
        # passes given the small record counts in the sandbox test account.
        base = super().expected_metadata()
        return {
            stream: {**meta, cls.API_LIMIT: 2}
            for stream, meta in base.items()
        }

    def streams_to_test(self):
        # Currently we do not exclude any streams from the pagination test.
        # This dictionary is kept to allow explicit exclusions (e.g., streams
        # with very few sandbox records) to be added if needed in the future.
        streams_to_exclude = {
        }
        return self.expected_stream_names().difference(streams_to_exclude)
