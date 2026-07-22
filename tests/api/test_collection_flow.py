import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_app.config import Settings
from agent_app.infrastructure.database import create_engine_and_session
from agent_app.infrastructure.models import Base
from agent_app.infrastructure.secrets import FileSecretStore
from agent_app.main import create_app


FIXTURE = json.loads(
    Path("tests/fixtures/job_snapshot.json").read_text(encoding="utf-8")
)
JOB_LIST_URL = "https://www.zhipin.com/web/geek/jobs"


@pytest.fixture
def flow_client(tmp_path):
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


def browser_headers(client):
    return {"X-Agent-Token": client.app.state.browser_token}


def create_collection(client, *, limit=2):
    batch = client.post(
        "/api/v1/batches",
        headers=app_headers(client),
        json={"limit": limit, "source_url": JOB_LIST_URL},
    ).json()
    started = client.post(
        f"/api/v1/batches/{batch['id']}/collect", headers=app_headers(client)
    )
    assert started.status_code == 202
    return batch, started.json()


def take_task(client, worker="test-browser"):
    response = client.get(
        f"/api/v1/browser/tasks/next?worker_id={worker}",
        headers=browser_headers(client),
    )
    assert response.status_code == 200
    return response.json()


def post_snapshot(client, batch_id, suffix):
    body = deepcopy(FIXTURE)
    body["encrypt_job_id"] = f"job-{suffix}"
    body["security_id"] = f"security-{suffix}"
    body["lid"] = f"lid-{suffix}"
    body["title"] = f"Python 后端工程师 {suffix}"
    response = client.post(
        f"/api/v1/browser/batches/{batch_id}/snapshots",
        headers=browser_headers(client),
        json=body,
    )
    assert response.status_code == 200


def resolve(client, task_id, body):
    return client.post(
        f"/api/v1/browser/tasks/{task_id}/result",
        headers=browser_headers(client),
        json={"worker_id": "test-browser", **body},
    )


def test_collection_result_advances_batch(flow_client):
    batch, started = create_collection(flow_client)
    task = take_task(flow_client)
    assert started["task_id"] == task["id"]
    assert task["type"] == "collect_batch"
    post_snapshot(flow_client, batch["id"], "one")
    post_snapshot(flow_client, batch["id"], "two")

    response = resolve(
        flow_client,
        task["id"],
        {"ok": True, "result": {"collected_count": 2, "exhausted": False}},
    )

    assert response.status_code == 200
    current = flow_client.get(
        f"/api/v1/batches/{batch['id']}", headers=app_headers(flow_client)
    ).json()
    assert current["status"] == "collected"
    assert current["counts"]["snapshots"] == 2


def test_collect_start_is_idempotent_and_does_not_create_two_tasks(flow_client):
    batch, first = create_collection(flow_client, limit=1)
    second = flow_client.post(
        f"/api/v1/batches/{batch['id']}/collect", headers=app_headers(flow_client)
    )
    assert second.status_code == 202
    assert second.json()["task_id"] == first["task_id"]
    assert take_task(flow_client)["id"] == first["task_id"]
    assert flow_client.get(
        "/api/v1/browser/tasks/next?worker_id=another-browser",
        headers=browser_headers(flow_client),
    ).status_code == 204


def test_collection_count_mismatch_does_not_resolve_or_advance(flow_client):
    batch, _ = create_collection(flow_client)
    task = take_task(flow_client)
    post_snapshot(flow_client, batch["id"], "one")

    response = resolve(
        flow_client,
        task["id"],
        {"ok": True, "result": {"collected_count": 2, "exhausted": False}},
    )

    assert response.status_code == 409
    current = flow_client.get(
        f"/api/v1/batches/{batch['id']}", headers=app_headers(flow_client)
    ).json()
    assert current["status"] == "collecting"


def test_security_result_pauses_batch_without_deleting_snapshots(flow_client):
    batch, _ = create_collection(flow_client)
    task = take_task(flow_client)
    post_snapshot(flow_client, batch["id"], "one")

    response = resolve(
        flow_client,
        task["id"],
        {
            "ok": False,
            "result": {"collected_count": 1},
            "error_code": "paused_security",
            "error_message": "security check",
        },
    )

    assert response.status_code == 200
    current = flow_client.get(
        f"/api/v1/batches/{batch['id']}", headers=app_headers(flow_client)
    ).json()
    assert current["status"] == "paused_security"
    assert current["counts"]["snapshots"] == 1
