"""Test that tap respects the configured start_date for INCREMENTAL streams."""
from base import TapInvoicedBaseTest
from tap_tester.base_suite_tests.start_date_test import StartDateTest


class TapInvoicedStartDateTest(StartDateTest, TapInvoicedBaseTest):
    """Instantiate start date according to the desired data set and run the test."""

    @staticmethod
    def name():
        return "tap_tester_tap_invoiced_start_date_test"

    def streams_to_test(self):
        # All six streams are INCREMENTAL.
        # NOTE: obeys_start_date=False for all streams because the Invoiced API
        # accepts `updated_after` as an epoch integer (set from bookmark/start_date),
        # so start-date filtering is applied but not via a named start_date query param.
        # Exclude streams that rarely have data old enough to exercise the window:
        streams_to_exclude = set()
        return self.expected_stream_names().difference(streams_to_exclude)

    @property
    def start_date_1(self):
        return "2015-03-25T00:00:00Z"

    @property
    def start_date_2(self):
        return "2017-01-25T00:00:00Z"
