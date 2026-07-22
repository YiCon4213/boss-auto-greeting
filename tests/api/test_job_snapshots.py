import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from agent_app.application.batches import BatchService
from agent_app.config import Settings
from agent_app.infrastructure.database import create_engine_and_session
from agent_app.infrastructure.models import AuditEvent, Base, JobSnapshot
from agent_app.infrastructure.repositories import BatchRepository
from agent_app.infrastructure.secrets import FileSecretStore
from agent_app.main import create_app


FIXTURE = Path("tests/fixtures/job_snapshot.json")
JOB_LIST_URL = "https://www.zhipin.com/web/geek/jobs"


@pytest.fixture
def snapshot_client(tmp_path):
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


def headers(client, scope):
    return {"X-Agent-Token": getattr(client.app.state, f"{scope}_token")}


def create_batch(client, session_factory, *, collecting=True):
    body = client.post(
        "/api/v1/batches",
        headers=headers(client, "app"),
        json={"source_url": JOB_LIST_URL},
    ).json()
    if collecting:
        with session_factory() as session:
            BatchService(BatchRepository(session)).transition(
                body["id"], "start_collection"
            )
    return body


def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_snapshot_requires_browser_scope_and_server_computed_identity(snapshot_client):
    client, session_factory = snapshot_client
    batch = create_batch(client, session_factory)
    body = payload()
    body["job_identity_key"] = "forged"

    assert client.post(
        f"/api/v1/browser/batches/{batch['id']}/snapshots", json=payload()
    ).status_code == 401
    response = client.post(
        f"/api/v1/browser/batches/{batch['id']}/snapshots",
        headers=headers(client, "browser"),
        json=body,
    )
    assert response.status_code == 422


def test_duplicate_snapshot_returns_original_without_mutation(snapshot_client):
    client, session_factory = snapshot_client
    batch = create_batch(client, session_factory)
    url = f"/api/v1/browser/batches/{batch['id']}/snapshots"
    original = payload()

    first = client.post(url, headers=headers(client, "browser"), json=original)
    changed = {**original, "description": "不能覆盖原快照"}
    second = client.post(url, headers=headers(client, "browser"), json=changed)

    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    assert second.json()["payload"]["description"] == original["description"]
    with session_factory() as session:
        assert session.scalar(select(func.count(JobSnapshot.id))) == 1
        assert session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.event_type == "job_snapshot_duplicate"
            )
        ) == 1


def test_snapshot_rejects_missing_identity_and_non_collecting_batch(snapshot_client):
    client, session_factory = snapshot_client
    collecting = create_batch(client, session_factory)
    missing_identity = {
        **payload(),
        "encrypt_job_id": "",
        "security_id": "",
        "lid": "",
    }
    assert client.post(
        f"/api/v1/browser/batches/{collecting['id']}/snapshots",
        headers=headers(client, "browser"),
        json=missing_identity,
    ).status_code == 422

    draft = create_batch(client, session_factory, collecting=False)
    response = client.post(
        f"/api/v1/browser/batches/{draft['id']}/snapshots",
        headers=headers(client, "browser"),
        json=payload(),
    )
    assert response.status_code == 409
