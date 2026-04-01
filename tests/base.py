import os

from tap_tester.base_suite_tests.base_case import BaseCase


class TapInvoicedBaseTest(BaseCase):
    """Setup expectations for test sub classes.

    Metadata describing streams. A bunch of shared methods that are used
    in tap-tester tests. Shared tap-specific methods (as needed).
    """

    start_date = "2019-01-01T00:00:00Z"

    @staticmethod
    def tap_name():
        """The name of the tap."""
        return "tap-invoiced"

    @staticmethod
    def get_type():
        """The Stitch connection type slug.
        Derived: "platform." + "invoiced" (from tap-invoiced with tap- stripped).
        """
        return "platform.invoiced"

    def setUp(self, *args, **kwargs):
        """Fail fast with a clear message when required credential env vars are absent."""
        missing = [v for v in ["TAP_INVOICED_API_KEY"] if not os.getenv(v)]
        if missing:
            raise Exception(
                f"Missing required environment variables: {missing}\n"
                "Set them before running live integration tests:\n"
                "  $env:TAP_INVOICED_API_KEY = '<your-api-key>'"
            )
        super().setUp(*args, **kwargs)

    def get_properties(self, original: bool = True):
        """Configuration properties required for the tap."""
        return_value = {
            "start_date": self.start_date,
            "sandbox": "true",
        }
        if original:
            return return_value

        return_value["start_date"] = self.start_date
        return return_value

    @staticmethod
    def get_credentials():
        """Authentication information for the test account.
        Values are read from environment variables — never hardcode credentials.
        """
        return {
            "api_key": os.getenv("TAP_INVOICED_API_KEY"),
        }

    @classmethod
    def expected_metadata(cls):
        """The expected streams and metadata about the streams."""
        return {
            "credit_notes": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"updated_at"},
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100,
            },
            "customers": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"updated_at"},
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100,
            },
            "estimates": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"updated_at"},
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100,
            },
            "invoices": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"updated_at"},
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100,
            },
            "plans": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"updated_at"},
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100,
            },
            "subscriptions": {
                cls.PRIMARY_KEYS: {"id"},
                cls.REPLICATION_METHOD: cls.INCREMENTAL,
                cls.REPLICATION_KEYS: {"updated_at"},
                cls.OBEYS_START_DATE: False,
                cls.API_LIMIT: 100,
            },
        }
