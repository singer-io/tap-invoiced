#!/usr/bin/env python3
import json
import singer
import invoiced
from singer import utils
from tap_invoiced.discover import discover_streams
from tap_invoiced.sync import sync_streams

REQUIRED_CONFIG_KEYS = ["start_date", "api_key"]
LOGGER = singer.get_logger()


def _build_client(config):
    """Build and return an invoiced.Client from the tap config."""
    sandbox = config.get("sandbox", False)
    is_sandbox = sandbox if isinstance(sandbox, bool) else str(sandbox).lower() == "true"
    return invoiced.Client(config["api_key"], is_sandbox)


@utils.handle_top_exception(LOGGER)
def main():

    # Parse command line arguments
    args = utils.parse_args(REQUIRED_CONFIG_KEYS)

    # If discover flag was passed, run discovery mode and dump output to stdout
    if args.discover:
        client = _build_client(args.config)
        catalog = discover_streams(client)
        print(json.dumps(catalog, indent=2))
    # Otherwise run in sync mode
    elif args.catalog:
        try:
            sync_streams(args.config, args.state, args.catalog)
        except Exception as e:
            LOGGER.critical(e)
            raise e


if __name__ == "__main__":
    main()
