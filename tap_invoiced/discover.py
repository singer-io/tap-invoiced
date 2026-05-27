import os
import json

import singer
from singer import metadata
from invoiced.errors import ApiError

from tap_invoiced.stream_access import check_stream_access

LOGGER = singer.get_logger()

KEY_PROPERTIES = ["id"]
REPLICATION_KEY = "updated_at"

STREAM_SDK_OBJECTS = {
    "credit_notes": "CreditNote",
    "customers": "Customer",
    "estimates": "Estimate",
    "invoices": "Invoice",
    "plans": "Plan",
    "subscriptions": "Subscription",
}


class _InvoicedAuthError(Exception):
    """Raised internally when an API probe returns HTTP 401 or 403."""


def _check_stream_access(client, stream_name):
    """
    Probe the invoiced endpoint for *stream_name* with a single-record request
    to verify that the credentials have read access.

    Returns True if accessible, False on HTTP 401/403.
    Any other exception is re-raised so genuine connectivity problems surface.
    """
    sdk_attr = STREAM_SDK_OBJECTS.get(stream_name)
    if sdk_attr is None:
        return True

    sdk_object = getattr(client, sdk_attr)

    def _probe():
        try:
            sdk_object.list(per_page=1, page=1)
        except ApiError as exc:
            if getattr(exc, "http_status", None) in (401, 403):
                raise _InvoicedAuthError(str(exc)) from exc
            raise

    return check_stream_access(
        stream_name,
        probe_fn=_probe,
        auth_error_types=_InvoicedAuthError,
    )


def discover_streams(client=None):
    raw_schemas = load_schemas()
    streams = []

    for schema_name, schema in raw_schemas.items():
        # Skip streams that the credentials cannot read.
        if client is not None and not _check_stream_access(client, schema_name):
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
