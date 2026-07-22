import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from agent_app.application.profiles import ProfileService
from agent_app.config import Settings
from agent_app.domain.llm_schemas import AnalysisModelOutput, GreetingModelOutput
from agent_app.domain.schemas import ProfileUpdate
from agent_app.infrastructure.database import create_engine_and_session
from agent_app.infrastructure.llm import ModelCallError
from agent_app.infrastructure.models import (
    ApprovalVersion,
    Base,
    Batch,
    BrowserTask,
    DeliveryItem,
    JobSnapshot,
)
from agent_app.infrastructure.repositories import ProfileRepository
from agent_app.infrastructure.secrets import FileSecretStore
from agent_app.main import create_app


SNAPSHOT_PAYLOAD = json.loads(
    Path("tests/fixtures/job_snapshot.json").read_text(encoding="utf-8")
)


class FakePhase3Client:
    model = "test-model"

    def __init__(self, *, analysis_error=False, greeting_fact="Python"):
        self.analysis_error = analysis_error
        self.greeting_fact = greeting_fact
        self.analysis_calls = 0

    async def analyze(self, payload):
        self.analysis_calls += 1
        if self.analysis_error:
            raise ModelCallError("safe analysis failure")
        return AnalysisModelOutput(
            target_score=80,
            personal_score=70,
            target_reasons=["方向一致"],
            personal_matches=["Python"],
            cautions=[],
        )

    async def generate_greeting(self, payload):
        return GreetingModelOutput(
            greeting="老师您好，我的 Python 和 AI Agent 项目经验与岗位要求较为匹配，期待进一步沟通。",
            used_facts=[self.greeting_fact],
        )


@pytest.fixture
def phase3_client(tmp_path, request):
    fake = getattr(request, "param", FakePhase3Client())
    settings = Settings(data_dir=tmp_path)
    engine, session_factory = create_engine_and_session(settings)
    Base.metadata.create_all(engine)
    with session_factory() as session:
        ProfileService(ProfileRepository(session)).save(
            ProfileUpdate(
                target_roles=["AI Agent 工程师"],
                skills=["Python", "AI Agent"],
            )
        )
        batch = Batch(
            status="collected",
            limit=1,
            analysis_enabled=True,
            greeting_enabled=True,
            source_url="https://www.zhipin.com/web/geek/jobs",
            counts={"snapshots": 1},
        )
        session.add(batch)
        session.flush()
        snapshot = JobSnapshot(
            batch_id=batch.id,
            job_identity_key="job:job-123|security:security-123|lid:lid-123",
            jd_fingerprint="fingerprint",
            payload=SNAPSHOT_PAYLOAD,
        )
        session.add(snapshot)
        session.commit()
        batch_id = batch.id
        snapshot_id = snapshot.id

    app = create_app(
        settings,
        secret_store=FileSecretStore(tmp_path / "secrets.json"),
        session_factory=session_factory,
        llm_client=fake,
    )
    with TestClient(app) as client:
        yield client, session_factory, batch_id, snapshot_id
    engine.dispose()


def headers(client):
    return {"X-Agent-Token": client.app.state.app_token}


def analyze(client, batch_id):
    return client.post(f"/api/v1/batches/{batch_id}/analyze", headers=headers(client))


def review(client, batch_id):
    return client.get(f"/api/v1/batches/{batch_id}/review", headers=headers(client))


def test_analysis_review_edit_and_immutable_approval_flow(phase3_client):
    client, session_factory, batch_id, snapshot_id = phase3_client

    started = analyze(client, batch_id)
    reviewed = review(client, batch_id)
    edited_text = "老师您好，我的 Python 项目经验和岗位要求匹配，希望进一步沟通。"
    edited = client.patch(
        f"/api/v1/batches/{batch_id}/drafts/{snapshot_id}",
        headers=headers(client),
        json={"selected": True, "greeting": edited_text},
    )
    approved = client.post(
        f"/api/v1/batches/{batch_id}/approve",
        headers=headers(client),
        json={
            "items": [
                {"snapshot_id": snapshot_id, "selected": True, "greeting": edited_text}
            ]
        },
    )

    assert started.status_code == 202
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "awaiting_approval"
    assert reviewed.json()["items"][0]["selected"] is True
    assert edited.status_code == 200
    assert edited.json()["greeting"] == edited_text
    assert approved.status_code == 200
    assert approved.json()["delivery_item_count"] == 1

    with session_factory() as session:
        item = session.scalar(select(DeliveryItem))
        assert item.final_greeting == edited_text
        assert item.payload["job_identity_key"].startswith("job:job-123")
        assert session.scalar(select(func.count(ApprovalVersion.id))) == 1
        assert session.scalar(
            select(func.count(BrowserTask.id)).where(
                BrowserTask.task_type == "execute_delivery"
            )
        ) == 0


def test_repeated_approval_is_idempotent_and_approved_draft_is_locked(phase3_client):
    client, _, batch_id, snapshot_id = phase3_client
    analyze(client, batch_id)
    body = {
        "items": [
            {
                "snapshot_id": snapshot_id,
                "selected": True,
                "greeting": "老师您好，我的 Python 项目经验与岗位要求匹配，期待进一步沟通。",
            }
        ]
    }

    first = client.post(
        f"/api/v1/batches/{batch_id}/approve", headers=headers(client), json=body
    )
    second = client.post(
        f"/api/v1/batches/{batch_id}/approve", headers=headers(client), json=body
    )
    edit = client.patch(
        f"/api/v1/batches/{batch_id}/drafts/{snapshot_id}",
        headers=headers(client),
        json={"selected": False, "greeting": "批准后不得修改这段话术。"},
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["approval_version_id"] == second.json()["approval_version_id"]
    assert edit.status_code == 409


def test_empty_selection_creates_immutable_empty_approval(phase3_client):
    client, _, batch_id, snapshot_id = phase3_client
    analyze(client, batch_id)

    response = client.post(
        f"/api/v1/batches/{batch_id}/approve",
        headers=headers(client),
        json={"items": [{"snapshot_id": snapshot_id, "selected": False, "greeting": ""}]},
    )

    assert response.status_code == 200
    assert response.json()["delivery_item_count"] == 0


@pytest.mark.parametrize(
    "phase3_client",
    [FakePhase3Client(analysis_error=True), FakePhase3Client(greeting_fact="不存在的经历")],
    indirect=True,
)
def test_failed_analysis_or_generation_cannot_be_approved(phase3_client):
    client, _, batch_id, snapshot_id = phase3_client
    assert analyze(client, batch_id).status_code == 202

    response = client.post(
        f"/api/v1/batches/{batch_id}/approve",
        headers=headers(client),
        json={
            "items": [
                {
                    "snapshot_id": snapshot_id,
                    "selected": True,
                    "greeting": "老师您好，这条失败记录不能进入批准队列，必须先修复。",
                }
            ]
        },
    )

    assert response.status_code == 409


def test_analyzing_batch_does_not_schedule_a_second_job(phase3_client):
    client, session_factory, batch_id, _ = phase3_client
    with session_factory() as session:
        batch = session.get(Batch, batch_id)
        batch.status = "analyzing"
        session.commit()
    fake = client.app.state.llm_client

    first = analyze(client, batch_id)
    second = analyze(client, batch_id)

    assert first.status_code == second.status_code == 202
    assert fake.analysis_calls == 0
