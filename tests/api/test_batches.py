import pytest
from fastapi.testclient import TestClient

from agent_app.config import Settings
from agent_app.infrastructure.database import create_engine_and_session
from agent_app.infrastructure.models import Base
from agent_app.infrastructure.secrets import FileSecretStore
from agent_app.main import create_app


@pytest.fixture
def batch_client(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine, session_factory = create_engine_and_session(settings)
    Base.metadata.create_all(engine)
    app = create_app(
        settings,
        secret_store=FileSecretStore(tmp_path / "secrets.json"),
        session_factory=session_factory,
    )
    with TestClient(app) as client:
        yield client
    engine.dispose()


def app_headers(client):
    return {"X-Agent-Token": client.app.state.app_token}


def test_batch_defaults_to_ten_jobs_and_draft(batch_client):
    response = batch_client.post(
        "/api/v1/batches",
        json={"source_url": "https://www.zhipin.com/web/geek/jobs"},
        headers=app_headers(batch_client),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["limit"] == 10
    assert body["status"] == "draft"
    assert body["available_actions"] == ["start_collection", "cancel"]

    loaded = batch_client.get(
        f"/api/v1/batches/{body['id']}", headers=app_headers(batch_client)
    )
    assert loaded.status_code == 200
    assert loaded.json() == body


@pytest.mark.parametrize(
    "source_url",
    [
        "http://www.zhipin.com/web/geek/jobs",
        "https://evil.example/web/geek/jobs",
        "https://www.zhipin.com/web/geek/chat",
    ],
)
def test_batch_rejects_non_job_list_sources(batch_client, source_url):
    response = batch_client.post(
        "/api/v1/batches",
        json={"source_url": source_url},
        headers=app_headers(batch_client),
    )
    assert response.status_code == 422
