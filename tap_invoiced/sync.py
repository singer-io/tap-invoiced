import singer
from singer import utils, metadata, Transformer
from datetime import datetime, timezone
import invoiced
import requests
import backoff
from invoiced.errors import ApiConnectionError, ApiError, RateLimitError

from tap_invoiced.constants import STREAM_SDK_OBJECTS

LOGGER = singer.get_logger()
REPLICATION_KEY = "updated_at"

def sync_streams(config, state, catalog):

    # Build the Invoiced client
    # config values are _always_ strings.
    is_sandbox = config.get('sandbox') == 'true'
    client = invoiced.Client(config['api_key'], is_sandbox)

    # Find the user-selected streams
    selected_stream_ids = get_selected_streams(catalog)

    # Loop over streams in catalog
    for stream in catalog.streams:
        stream_id = stream.tap_stream_id
        if stream_id in selected_stream_ids:
            # Write out the schemas
            schema_dict = stream.schema.to_dict()
            stream_metadata = metadata.to_map(stream.metadata)
            singer.write_schema(stream_id, schema_dict,
                                stream.key_properties)

            # Then write out the records
            sync(client, config, state, stream_id,
                 schema_dict, stream_metadata)


def get_selected_streams(catalog):
    '''
      Gets selected streams.  Checks schema's 'selected' first (legacy)
      and then checks metadata (current), looking for an empty breadcrumb
      and mdata with a 'selected' entry
    '''
    selected_streams = []
    for stream in catalog.streams:
        stream_metadata = metadata.to_map(stream.metadata)
        # stream metadata will have an empty breadcrumb
        if metadata.get(stream_metadata, (), "selected"):
            selected_streams.append(stream.tap_stream_id)

    return selected_streams

@backoff.on_exception(
    backoff.expo,
    (ApiConnectionError, ApiError),
    max_tries=5,
    factor=2
)
@backoff.on_exception(
    backoff.constant,
    RateLimitError,
    max_tries=5,
    jitter=None,
    interval=60
)
def fetch_with_backoff_retry(sdkObject, page, bookmark):
    objects, metadata = sdkObject.list(
        per_page=100,
        page=page,
        include="updated_at",
        sort="updated_at ASC",
        updated_after=bookmark
    )
    return objects, metadata

def sync(client, config, state, stream_name, schema, stream_metadata):
    '''
      Syncs a given stream.
    '''
    LOGGER.info('Syncing stream:' + stream_name)

    extraction_time = singer.utils.now()
    replication_key = "updated_at"

    # Find our bookmark where our sync last ended
    # (or the start date if it's a new sync)
    stream_bookmark = singer.get_bookmark(state, stream_name, replication_key)
    if isinstance(stream_bookmark, str):
        stream_bookmark = int(utils.strptime_to_utc(stream_bookmark).timestamp())
    bookmark = stream_bookmark or \
        int(utils.strptime_to_utc(config["start_date"]).timestamp())
    max_bookmark = bookmark

    with Transformer(singer.UNIX_SECONDS_INTEGER_DATETIME_PARSING) \
            as transformer:
        hasMore = True
        page = 1
        while hasMore:
            LOGGER.info("Fetching page # {} of {}".format(str(page),
                                                          stream_name))
            sdkObject = getattr(client, STREAM_SDK_OBJECTS[stream_name])

            # Call the retry-wrapped function
            objects, listMetadata = fetch_with_backoff_retry(sdkObject, page, bookmark)

            LOGGER.info("{} objects returned".format(len(objects)))

            for obj in objects:
                # Client-side guard: skip records older than the bookmark
                # before paying the cost of dict(), clamping, and transform.
                # Some API endpoints (e.g. plans) ignore the updated_after
                # parameter and return all records regardless; filtering here
                # ensures correctness for every stream.
                stream_bookmark = obj.get(replication_key)
                if stream_bookmark is not None and stream_bookmark < bookmark:
                    continue

                rec = dict(obj)
                rec["created_at"] = max(0, rec["created_at"])
                rec["updated_at"] = max(0, rec["updated_at"])
                rec = transformer.transform(rec,
                                            schema,
                                            metadata=stream_metadata)

                singer.write_record(stream_name,
                                    rec,
                                    time_extracted=extraction_time)

                if stream_bookmark is not None and stream_bookmark > max_bookmark:
                    max_bookmark = stream_bookmark
                    bookmark_iso = datetime.fromtimestamp(
                        max_bookmark, tz=timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    singer.write_bookmark(state,
                                          stream_name,
                                          replication_key,
                                          bookmark_iso)

            # write state after every 100 records
            singer.write_state(state)

            # load next page, if there is one
            hasMore = "next" in listMetadata.links.keys()
            page += 1
