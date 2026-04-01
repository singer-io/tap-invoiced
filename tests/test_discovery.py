"""Test tap discovery mode and metadata."""
from base import TapInvoicedBaseTest
from tap_tester.base_suite_tests.discovery_test import DiscoveryTest


class TapInvoicedDiscoveryTest(DiscoveryTest, TapInvoicedBaseTest):
    """Test tap discovery mode and metadata conforms to standards."""

    @staticmethod
    def name():
        return "tap_tester_tap_invoiced_discovery_test"

    def streams_to_test(self):
        return self.expected_stream_names()
