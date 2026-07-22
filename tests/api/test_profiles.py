import pytest
from fastapi.testclient import TestClient

from agent_app.config import Settings
from agent_app.infrastructure.database import create_engine_and_session
from agent_app.infrastructure.models import Base
from agent_app.infrastructure.secrets import FileSecretStore
from agent_app.main import create_app


@pytest.fixture
def profile_client(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine, session_factory = create_engine_and_session(settings)
    Base.metadata.create_all(engine)
    secret_store = FileSecretStore(tmp_path / "secrets.json")
    app = create_app(
        settings,
        secret_store=secret_store,
        session_factory=session_factory,
    )
    with TestClient(app) as client:
        yield client, secret_store, tmp_path / "boss_agent.sqlite3"
    engine.dispose()


def app_headers(client):
    return {"X-Agent-Token": client.app.state.app_token}


def test_profile_round_trip_preserves_visibility(profile_client):
    client, _, _ = profile_client
    payload = {
        "target_roles": ["AI 应用工程师"],
        "skills": ["Python", "FastAPI"],
        "email": "private@example.com",
        "field_visibility": {
            "target_roles": True,
            "skills": True,
            "email": False,
        },
    }

    saved = client.put(
        "/api/v1/profiles/current", json=payload, headers=app_headers(client)
    )
    loaded = client.get(
        "/api/v1/profiles/current", headers=app_headers(client)
    )

    assert saved.status_code == 200
    assert loaded.status_code == 200
    assert loaded.json()["target_roles"] == payload["target_roles"]
    assert loaded.json()["field_visibility"] == payload["field_visibility"]


def test_model_config_never_exposes_or_persists_api_key(profile_client):
    client, secret_store, database_path = profile_client
    payload = {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-test",
        "timeout_seconds": 45,
        "temperature": 0.3,
        "api_key": "top-secret-key",
    }

    saved = client.put(
        "/api/v1/settings/model", json=payload, headers=app_headers(client)
    )
    loaded = client.get(
        "/api/v1/settings/model", headers=app_headers(client)
    )

    assert saved.status_code == 200
    assert loaded.status_code == 200
    assert saved.json()["api_key_configured"] is True
    assert "api_key" not in saved.json()
    assert "api_key" not in loaded.json()
    assert secret_store.get("openai_api_key") == "top-secret-key"
    assert b"top-secret-key" not in database_path.read_bytes()
