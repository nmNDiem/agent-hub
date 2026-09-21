import pytest

from agent_hub_api.config import normalize_database_url


@pytest.mark.parametrize("scheme", ["postgresql://", "postgres://"])
def test_normalize_database_url_selects_asyncpg_dialect(scheme: str) -> None:
    value = f"{scheme}user:password@example.test:5432/database"

    normalized = normalize_database_url(value)

    assert normalized == "postgresql+asyncpg://user:password@example.test:5432/database"


def test_normalize_database_url_preserves_asyncpg_url() -> None:
    value = "postgresql+asyncpg://user:password@example.test:5432/database"

    assert normalize_database_url(value) == value


def test_normalize_database_url_rejects_non_postgresql_scheme() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        normalize_database_url("sqlite:///database.db")
