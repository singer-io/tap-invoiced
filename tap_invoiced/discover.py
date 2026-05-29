import os
import json

import singer
from singer import metadata

from tap_invoiced.stream_access import check_stream_access

LOGGER = singer.get_logger()

KEY_PROPERTIES = ["id"]
REPLICATION_KEY = "updated_at"


class InvoicedForbiddenError(Exception):
    """Raised when none of the streams are accessible with the given credentials."""


def discover_streams(client=None):
    raw_schemas = load_schemas()
    streams = []
    excluded_streams = []

    for schema_name, schema in raw_schemas.items():
        # Skip streams that the credentials cannot read.
        if client is not None and not check_stream_access(client, schema_name):
            excluded_streams.append(schema_name)
            continue

        # populate any metadata and stream's key properties here..
        stream_key_properties = KEY_PROPERTIES
        stream_metadata = get_metadata(schema,
                                       stream_key_properties,
                                       "INCREMENTAL",
                                       REPLICATION_KEY)

        # create and add catalog entry
        catalog_entry = {
            'stream': schema_name,
            'tap_stream_id': schema_name,
            'schema': schema,
            'metadata': stream_metadata,
            'key_properties': stream_key_properties
        }
        streams.append(catalog_entry)

    # If all streams are inaccessible, raise an exception.
    if client is not None and excluded_streams and not streams:
        raise InvoicedForbiddenError(
            "HTTP-error-code: 403, Error: The credentials do not have read access to any "
            "of the streams supported by the tap. Data collection cannot proceed due to "
            "lack of permissions."
        )

    # Log excluded streams as a single warning.
    if excluded_streams:
        LOGGER.warning(
            "The following stream(s) are not accessible with the provided credentials "
            "and have been excluded from the catalog: %s",
            ", ".join(excluded_streams),
        )

    return {'streams': streams}


def load_schemas():
    '''
      Load schemas from schemas folder
    '''
    schemas = {}

    for filename in os.listdir(get_abs_path('schemas')):
        path = get_abs_path('schemas') + '/' + filename
        file_raw = filename.replace('.json', '')
        with open(path) as file:
            schemas[file_raw] = json.load(file)

    return schemas


def get_abs_path(path):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)


def get_metadata(schema, key_properties, replication_method, replication_key):
    mdata = metadata.new()
    mdata = metadata.write(mdata,
                           (),
                           'table-key-properties',
                           key_properties)
    mdata = metadata.write(mdata,
                           (),
                           'forced-replication-method',
                           replication_method)

    if replication_key:
        mdata = metadata.write(mdata,
                               (),
                               'valid-replication-keys',
                               [replication_key])

    for field_name in schema['properties'].keys():
        if field_name in key_properties \
                or field_name in [replication_key, "updated"]:
            mdata = metadata.write(mdata,
                                   ('properties', field_name),
                                   'inclusion',
                                   'automatic')
        else:
            mdata = metadata.write(mdata,
                                   ('properties', field_name),
                                   'inclusion',
                                   'available')

    return metadata.to_list(mdata)
