import asyncio

import pytest

from agent_app.application.analysis import AnalysisService, recommendation_for
from agent_app.application.profiles import ProfileService
from agent_app.config import Settings
from agent_app.domain.llm_schemas import AnalysisModelOutput
from agent_app.domain.schemas import ProfileUpdate
from agent_app.infrastructure.database import create_engine_and_session
from agent_app.infrastructure.llm import ModelCallError
from agent_app.infrastructure.models import Base, Batch, JobSnapshot
from agent_app.infrastructure.repositories import ProfileRepository


class FakeLlmClient:
    model = "test-model"

    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error
        self.payloads: list[dict[str, object]] = []

    async def analyze(self, payload):
        self.payloads.append(payload)
        if self.error is not None:
            raise self.error
        return self.output


@pytest.fixture
def analysis_context(tmp_path):
    engine, session_factory = create_engine_and_session(Settings(data_dir=tmp_path))
    Base.metadata.create_all(engine)
    with session_factory() as session:
        ProfileService(ProfileRepository(session)).save(
            ProfileUpdate(
                target_roles=["AI Agent 工程师"],
                target_directions=["AI 应用"],
                skills=["Python", "FastAPI"],
                phone="13800000000",
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
            job_identity_key="job:one",
            jd_fingerprint="fingerprint",
            payload={
                "title": "AI Agent 工程师",
                "company": "示例公司",
                "description": "负责 Agent 平台开发，需要 Python 与 Go",
                "skills": ["Python", "Go"],
                "city": "深圳",
                "experience": "3-5年",
            },
        )
        session.add(snapshot)
        session.commit()
        yield session, snapshot.id
    engine.dispose()


def run(coroutine):
    return asyncio.run(coroutine)


@pytest.mark.parametrize(
    ("score", "expected"),
    [(29, "deselect"), (30, "cautious"), (59, "cautious"), (60, "recommend"), (100, "recommend")],
)
def test_recommendation_threshold_boundaries(score, expected):
    assert recommendation_for(score) == expected


def test_disabled_analysis_skips_model_and_selects_snapshot(analysis_context):
    session, snapshot_id = analysis_context
    client = FakeLlmClient()

    result = run(
        AnalysisService(session, client).analyze_snapshot(
            snapshot_id, analysis_enabled=False
        )
    )

    assert client.payloads == []
    assert result.status == "skipped"
    assert result.target_score is None
    assert result.selected_by_default is True


def test_personal_score_never_changes_target_selection(analysis_context):
    session, snapshot_id = analysis_context
    output = AnalysisModelOutput(
        target_score=30,
        personal_score=0,
        target_reasons=["方向达到谨慎阈值"],
        personal_matches=[],
        cautions=["画像未提供 Go 经历"],
    )
    client = FakeLlmClient(output=output)

    result = run(AnalysisService(session, client).analyze_snapshot(snapshot_id, analysis_enabled=True))

    assert result.recommendation == "cautious"
    assert result.selected_by_default is True
    assert result.cautions == ["画像未提供 Go 经历"]


def test_target_context_excludes_location_experience_and_private_profile(analysis_context):
    session, snapshot_id = analysis_context
    output = AnalysisModelOutput(
        target_score=80,
        personal_score=70,
        target_reasons=["方向一致"],
        personal_matches=["Python"],
        cautions=[],
    )
    client = FakeLlmClient(output=output)

    run(AnalysisService(session, client).analyze_snapshot(snapshot_id, analysis_enabled=True))

    payload = client.payloads[0]
    assert "city" not in payload["target_context"]
    assert "experience" not in payload["target_context"]
    assert "深圳" not in str(payload["target_context"])
    assert "3-5年" not in str(payload["target_context"])
    assert "13800000000" not in str(payload)


def test_model_failure_is_visible_but_not_selectable_or_approvable(analysis_context):
    session, snapshot_id = analysis_context
    client = FakeLlmClient(error=ModelCallError("safe failure"))

    result = run(AnalysisService(session, client).analyze_snapshot(snapshot_id, analysis_enabled=True))

    assert result.status == "analysis_failed"
    assert result.selected_by_default is False
    assert result.approvable is False
    assert result.error_code == "model_call_failed"
