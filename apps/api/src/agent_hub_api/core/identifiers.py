from uuid import UUID

from uuid6 import uuid7


def new_uuid_v7() -> UUID:
    """Generate an RFC 9562 UUIDv7 on the application server."""

    value = uuid7()
    if value.version != 7:
        raise RuntimeError("UUIDv7 provider returned an unexpected UUID version")
    return value
