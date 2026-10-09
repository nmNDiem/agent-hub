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


def test_provider_placeholders_are_not_treated_as_credentials() -> None:
    settings = EnvironmentOnlySettings.model_validate(
        {
            "openai_api_key": "REPLACE_ME_SERVER_ONLY",
            "qdrant_api_key": "REPLACE_ME_SERVER_ONLY",
            "qdrant_url": "https://<cluster>.cloud.qdrant.io",
            "embedding_model": "REPLACE_WITH_VERIFIED_MODEL",
            "embedding_dimensions": "REPLACE_WITH_VERIFIED_DIMENSIONS",
            "generation_model": "REPLACE_WITH_VERIFIED_MODEL",
        }
    )

    assert settings.openai_api_key is None
    assert settings.qdrant_api_key is None
    assert settings.qdrant_url is None
    assert settings.embedding_model is None
    assert settings.embedding_dimensions is None
    assert settings.generation_model is None


def test_agent_runtime_limits_reject_unbounded_provider_configuration() -> None:
    with pytest.raises(ValueError, match="total token budget"):
        EnvironmentOnlySettings.model_validate(
            {
                "agent_runtime_max_output_tokens": 100,
                "agent_runtime_max_total_tokens": 100,
            }
        )

    with pytest.raises(ValueError, match="20 chunks"):
        EnvironmentOnlySettings.model_validate(
            {"agent_runtime_max_knowledge_chunks": 21}
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("database_pool_size", 0, "pool size"),
        ("database_pool_max_overflow", -1, "pool overflow"),
        ("database_pool_timeout_seconds", 0, "pool timeout"),
        ("database_connect_timeout_seconds", 61, "connect timeout"),
    ],
)
def test_database_pool_limits_are_bounded(field: str, value: int, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        EnvironmentOnlySettings.model_validate({field: value})
