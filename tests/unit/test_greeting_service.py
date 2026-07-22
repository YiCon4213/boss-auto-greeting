import asyncio

import pytest

from agent_app.application.greetings import BASE_GREETING, GreetingService
from agent_app.application.profiles import ProfileService
from agent_app.config import Settings
from agent_app.domain.llm_schemas import GreetingModelOutput
from agent_app.domain.schemas import ProfileUpdate
from agent_app.infrastructure.database import create_engine_and_session
from agent_app.infrastructure.llm import ModelCallError
from agent_app.infrastructure.models import Analysis, Base, Batch, JobSnapshot
from agent_app.infrastructure.repositories import ProfileRepository


class FakeGreetingClient:
    model = "test-model"

    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error
        self.payloads: list[dict[str, object]] = []

    async def generate_greeting(self, payload):
        self.payloads.append(payload)
        if self.error is not None:
            raise self.error
        return self.output


@pytest.fixture
def greeting_context(tmp_path):
    engine, session_factory = create_engine_and_session(Settings(data_dir=tmp_path))
    Base.metadata.create_all(engine)
    with session_factory() as session:
        ProfileService(ProfileRepository(session)).save(
            ProfileUpdate(
                education=[{"school": "华南农业大学", "degree": "研究生"}],
                skills=["Python", "AI Agent"],
                projects=[{"name": "本地 Agent", "summary": "FastAPI 服务"}],
                availability={"internship_months": "3-6", "earliest_start": "3日内"},
                phone="13800000000",
                email="private@example.com",
                address="广东省私密地址",
            )
        )
        batch = Batch(
            status="analyzing",
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
            job_identity_key="job:one",
            jd_fingerprint="fingerprint",
            payload={
                "title": "AI Agent 工程师",
                "company": "示例公司",
                "description": "负责 Agent 平台开发，需要 Python",
                "skills": ["Python"],
            },
        )
        session.add(snapshot)
        session.flush()
        session.add(
            Analysis(
                batch_id=batch.id,
                job_snapshot_id=snapshot.id,
                status="completed",
                payload={
                    "target_score": 80,
                    "personal_score": 70,
                    "recommendation": "recommend",
                    "target_reasons": ["方向一致"],
                    "personal_matches": ["Python"],
                    "cautions": [],
                },
            )
        )
        session.commit()
        yield session, batch, snapshot.id
    engine.dispose()


def run(coroutine):
    return asyncio.run(coroutine)


def test_disabled_generation_returns_base_template_without_model(greeting_context):
    session, batch, snapshot_id = greeting_context
    batch.greeting_enabled = False
    session.commit()
    client = FakeGreetingClient()

    result = run(GreetingService(session, client).generate(snapshot_id))

    assert client.payloads == []
    assert result.source == "base_template"
    assert result.text == BASE_GREETING
    assert result.approvable is True
    assert result.approved_at is None


def test_model_generation_uses_only_traceable_profile_facts(greeting_context):
    session, _, snapshot_id = greeting_context
    client = FakeGreetingClient(
        output=GreetingModelOutput(
            greeting="老师您好，我的 Python 和 AI Agent 项目经验与岗位要求较为匹配，期待进一步沟通。",
            used_facts=["Python", "AI Agent"],
        )
    )

    result = run(GreetingService(session, client).generate(snapshot_id))

    assert result.status == "completed"
    assert result.source == "model"
    assert result.used_facts == ["Python", "AI Agent"]
    assert result.approvable is True
    request = str(client.payloads[0])
    assert "13800000000" not in request
    assert "private@example.com" not in request
    assert "广东省私密地址" not in request


def test_untraceable_model_fact_fails_without_template_fallback(greeting_context):
    session, _, snapshot_id = greeting_context
    client = FakeGreetingClient(
        output=GreetingModelOutput(
            greeting="老师您好，我有十年 Go 架构经验，和岗位要求非常匹配，期待进一步沟通。",
            used_facts=["十年 Go 架构经验"],
        )
    )

    result = run(GreetingService(session, client).generate(snapshot_id))

    assert result.status == "generation_failed"
    assert result.approvable is False
    assert result.text == ""
    assert result.error_code == "unverified_profile_fact"


def test_sensitive_values_are_removed_from_model_text(greeting_context):
    session, _, snapshot_id = greeting_context
    client = FakeGreetingClient(
        output=GreetingModelOutput(
            greeting="老师您好，我擅长 Python，电话13800000000，邮箱private@example.com，期待进一步沟通。",
            used_facts=["Python"],
        )
    )

    result = run(GreetingService(session, client).generate(snapshot_id))

    assert "13800000000" not in result.text
    assert "private@example.com" not in result.text
    assert result.approvable is True


def test_final_model_failure_is_not_approvable(greeting_context):
    session, _, snapshot_id = greeting_context
    client = FakeGreetingClient(error=ModelCallError("safe failure"))

    result = run(GreetingService(session, client).generate(snapshot_id))

    assert result.status == "generation_failed"
    assert result.approvable is False
    assert result.error_code == "model_call_failed"
    assert result.text == ""
