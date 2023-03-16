import singer
from singer import utils, metadata, Transformer
import invoiced

LOGGER = singer.get_logger()
REPLICATION_KEY = "updated_at"
STREAM_SDK_OBJECTS = {
    'credit_notes': 'CreditNote',
    'customers': 'Customer',
    'estimates': 'Estimate',
    'invoices': 'Invoice',
    'plans': 'Plan',
    'subscriptions': 'Subscription',
    'transactions': 'Transaction',
}


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
            objects, listMetadata = sdkObject.list(
                    per_page=100,
                    page=page,
                    include="updated_at",
                    sort="updated_at ASC",
                    updated_after=bookmark)
            LOGGER.info("{} objects returned".format(len(objects)))

            for obj in objects:
                rec = dict(obj)
                rec["created_at"] = max(0, rec["created_at"])
                rec["updated_at"] = max(0, rec["updated_at"])
                rec = transformer.transform(rec,
                                            schema,
                                            metadata=stream_metadata)

                singer.write_record(stream_name,
                                    rec,
                                    time_extracted=extraction_time)

                stream_bookmark = obj.get(replication_key)

                if stream_bookmark > max_bookmark:
                    max_bookmark = stream_bookmark
                    singer.write_bookmark(state,
                                          stream_name,
                                          replication_key,
                                          max_bookmark)

            # write state after every 100 records
            singer.write_state(state)

            # load next page, if there is one
            hasMore = "next" in listMetadata.links.keys()
            page += 1
