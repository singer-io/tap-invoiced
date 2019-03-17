import os
import json
from singer import metadata

KEY_PROPERTIES = ["id"]
REPLICATION_KEY = "updated_at"


def discover_streams():
    raw_schemas = load_schemas()
    streams = []

    for schema_name, schema in raw_schemas.items():
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
