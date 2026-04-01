"""Test that tap respects the configured start_date for INCREMENTAL streams."""
from base import TapInvoicedBaseTest
from tap_tester.base_suite_tests.start_date_test import StartDateTest


class TapInvoicedStartDateTest(StartDateTest, TapInvoicedBaseTest):
    """Instantiate start date according to the desired data set and run the test."""

    @staticmethod
    def name():
        return "tap_tester_tap_invoiced_start_date_test"

    def streams_to_test(self):
        # Only customers has sandbox records spread across multiple dates
        # (some from 2025, most from 2026), so it is the only stream where
        # sync_1 (start before 2025 data) returns more records than
        # sync_2 (start in 2026, after the old 2025 records).
        # All other streams only have data from 2026-04-01, so both start
        # dates would return identical counts, causing the assertGreater to fail.
        streams_to_exclude = {
            "invoices",
            "plans",
            "subscriptions",
            "estimates",
            "credit_notes",
        }
        return self.expected_stream_names().difference(streams_to_exclude)

    @property
    def start_date_1(self):
        # Before the oldest customers records (2025-06-xx) — captures all data.
        return "2025-01-01T00:00:00Z"

    @property
    def start_date_2(self):
        # After the 2025 customers records but before the 2026-04-01 data —
        # filters out the older records so sync_2_count < sync_1_count.
        return "2026-01-01T00:00:00Z"
