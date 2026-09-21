import pytest
from pydantic import ValidationError

from app.core.settings import Settings


BASE_SETTINGS = {
    "database_url": "postgresql://localhost/test",
    "openai_api_key": "test-openai-key",
    "llm_model": "test-llm-model",
    "embedding_model": "test-embedding-model",
    "tenant_id": "test-tenant",
    "secret_key": "test-secret-key",
}


def test_composer_secrets_are_required(monkeypatch):
    monkeypatch.delenv("ACOP_COMPOSER_JWT_SECRET", raising=False)
    monkeypatch.delenv("ACOP_COMPOSER_ISSUER_SECRET", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, **BASE_SETTINGS)

    missing_fields = {error["loc"][0] for error in exc_info.value.errors()}
    assert {"composer_jwt_secret", "composer_issuer_secret"} <= missing_fields


def test_composer_secrets_are_loaded_when_present(monkeypatch):
    monkeypatch.setenv("ACOP_COMPOSER_JWT_SECRET", "test-composer-jwt-secret")
    monkeypatch.setenv("ACOP_COMPOSER_ISSUER_SECRET", "test-composer-issuer-secret")

    settings = Settings(_env_file=None, **BASE_SETTINGS)

    assert settings.composer_jwt_secret == "test-composer-jwt-secret"
    assert settings.composer_issuer_secret == "test-composer-issuer-secret"
