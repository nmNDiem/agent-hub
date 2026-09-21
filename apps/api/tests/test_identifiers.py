from uuid import UUID

from agent_hub_api.identifiers import new_uuid_v7


def test_new_uuid_v7_returns_unique_rfc_9562_values() -> None:
    values = {new_uuid_v7() for _ in range(100)}

    assert len(values) == 100
    assert all(isinstance(value, UUID) for value in values)
    assert all(value.version == 7 for value in values)
    assert all(value.variant == "specified in RFC 4122" for value in values)
