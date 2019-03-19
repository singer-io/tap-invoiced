#!/usr/bin/env python3
import json
import singer
from singer import utils
from tap_invoiced.discover import discover_streams
from tap_invoiced.sync import sync_streams
import sys

REQUIRED_CONFIG_KEYS = ["start_date", "api_key"]
LOGGER = singer.get_logger()


@utils.handle_top_exception(LOGGER)
def main():

    # Parse command line arguments
    args = utils.parse_args(REQUIRED_CONFIG_KEYS)

    # If discover flag was passed, run discovery mode and dump output to stdout
    if args.discover:
        catalog = discover_streams()
        print(json.dumps(catalog, indent=2))
    # Otherwise run in sync mode
    elif args.catalog:
        try:
            sync_streams(args.config, args.state, args.catalog)
        except Exception as e:
            LOGGER.critical(e)
            sys.exit(1)


if __name__ == "__main__":
    main()
