import pytest
from fastapi.testclient import TestClient

from agent_app.application.browser_tasks import BrowserTaskService
from agent_app.config import Settings
from agent_app.infrastructure.database import create_engine_and_session
from agent_app.infrastructure.models import Base
from agent_app.infrastructure.secrets import FileSecretStore
from agent_app.main import create_app


@pytest.fixture
def browser_client(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine, session_factory = create_engine_and_session(settings)
    Base.metadata.create_all(engine)
    app = create_app(
        settings,
        secret_store=FileSecretStore(tmp_path / "secrets.json"),
        session_factory=session_factory,
    )
    with TestClient(app) as client:
        yield client, session_factory
    engine.dispose()


def browser_headers(client):
    return {"X-Agent-Token": client.app.state.browser_token}


def create_task(session_factory, key="pause:test"):
    with session_factory() as session:
        return BrowserTaskService(session).create("pause", {}, key).id


def test_browser_heartbeat_requires_browser_scope(browser_client):
    client, _ = browser_client
    assert client.post("/api/v1/browser/heartbeat").status_code == 401
    assert client.post(
        "/api/v1/browser/heartbeat",
        headers={"X-Agent-Token": client.app.state.app_token},
    ).status_code == 401
    response = client.post(
        "/api/v1/browser/heartbeat", headers=browser_headers(client)
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_next_returns_204_or_a_fixed_envelope(browser_client):
    client, session_factory = browser_client
    empty = client.get(
        "/api/v1/browser/tasks/next?worker_id=browser-1",
        headers=browser_headers(client),
    )
    assert empty.status_code == 204
    task_id = create_task(session_factory)
    response = client.get(
        "/api/v1/browser/tasks/next?worker_id=browser-1",
        headers=browser_headers(client),
    )
    assert response.status_code == 200
    assert response.json() == {
        "id": task_id,
        "type": "pause",
        "payload": {},
        "lease_seconds": 30,
    }


def test_ack_progress_and_result_enforce_worker_and_idempotency(browser_client):
    client, session_factory = browser_client
    task_id = create_task(session_factory, "pause:flow")
    client.get(
        "/api/v1/browser/tasks/next?worker_id=browser-1",
        headers=browser_headers(client),
    )
    wrong = client.post(
        f"/api/v1/browser/tasks/{task_id}/ack",
        headers=browser_headers(client),
        json={"worker_id": "browser-2"},
    )
    assert wrong.status_code == 409
    assert client.post(
        f"/api/v1/browser/tasks/{task_id}/ack",
        headers=browser_headers(client),
        json={"worker_id": "browser-1"},
    ).status_code == 200
    progress = {
        "worker_id": "browser-1",
        "sequence": 1,
        "status": "paused",
        "detail": {},
    }
    assert client.post(
        f"/api/v1/browser/tasks/{task_id}/progress",
        headers=browser_headers(client),
        json=progress,
    ).json() == {"accepted": True}
    assert client.post(
        f"/api/v1/browser/tasks/{task_id}/progress",
        headers=browser_headers(client),
        json=progress,
    ).json() == {"accepted": False}
    result = {
        "worker_id": "browser-1",
        "ok": True,
        "result": {"paused": True},
    }
    first = client.post(
        f"/api/v1/browser/tasks/{task_id}/result",
        headers=browser_headers(client),
        json=result,
    )
    repeated = client.post(
        f"/api/v1/browser/tasks/{task_id}/result",
        headers=browser_headers(client),
        json=result,
    )
    assert first.status_code == repeated.status_code == 200
    assert repeated.json()["status"] == "resolved"
    different = client.post(
        f"/api/v1/browser/tasks/{task_id}/result",
        headers=browser_headers(client),
        json={"worker_id": "browser-1", "ok": False, "error_code": "changed"},
    )
    assert different.status_code == 409


def test_unknown_browser_task_returns_404(browser_client):
    client, _ = browser_client
    response = client.post(
        "/api/v1/browser/tasks/missing/ack",
        headers=browser_headers(client),
        json={"worker_id": "browser-1"},
    )
    assert response.status_code == 404
