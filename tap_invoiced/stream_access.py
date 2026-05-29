from invoiced.errors import ApiError

from tap_invoiced.constants import STREAM_SDK_OBJECTS


class InvoicedStreamAccessError(Exception):
    """Raised when a stream cannot be accessed due to an auth failure (HTTP 401/403)."""


def check_stream_access(client, stream_name):
    """
    Probe the Invoiced API endpoint for *stream_name* with a minimal request
    to verify that the credentials have read access.

    Returns normally if accessible.
    Raises InvoicedStreamAccessError on HTTP 401/403.
    Any other API error is re-raised so genuine connectivity problems surface.
    """
    sdk_attr = STREAM_SDK_OBJECTS.get(stream_name)
    if sdk_attr is None:
        return

    sdk_object = getattr(client, sdk_attr)

    try:
        sdk_object.list(per_page=1, page=1)
    except ApiError as exc:
        if getattr(exc, "http_status", None) in (401, 403):
            raise InvoicedStreamAccessError(stream_name) from exc
        raise
