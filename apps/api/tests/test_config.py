import pytest
from pydantic_settings import SettingsConfigDict
from pytest import MonkeyPatch

from agent_hub_api.core.config import Settings, normalize_database_url


class EnvironmentOnlySettings(Settings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")


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


def test_settings_use_unprefixed_environment_names(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@example.test/database")
    monkeypatch.setenv("JWT_SIGNING_KEY", "x" * 32)
    monkeypatch.setenv("CATALOG_CSV_MAX_ROWS", "250")

    settings = EnvironmentOnlySettings()

    assert settings.app_env == "test"
    assert settings.database_url == "postgresql+asyncpg://user:password@example.test/database"
    assert settings.jwt_signing_key == "x" * 32
    assert settings.catalog_csv_max_rows == 250
