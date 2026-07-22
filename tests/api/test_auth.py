import pytest
from fastapi.testclient import TestClient

from agent_app.config import Settings
from agent_app.infrastructure.secrets import FileSecretStore
from agent_app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(data_dir=tmp_path)
    secret_store = FileSecretStore(tmp_path / "secrets.json")
    with TestClient(create_app(settings, secret_store=secret_store)) as test_client:
        yield test_client


def test_business_api_rejects_missing_token(client):
    response = client.get("/api/v1/auth-check")
    assert response.status_code == 401


def test_business_api_rejects_wrong_token(client):
    response = client.get(
        "/api/v1/auth-check", headers={"X-Agent-Token": "wrong-token"}
    )
    assert response.status_code == 401


def test_business_api_accepts_app_token(client):
    response = client.get(
        "/api/v1/auth-check",
        headers={"X-Agent-Token": client.app.state.app_token},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
