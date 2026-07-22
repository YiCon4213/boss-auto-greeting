from agent_app.application.profiles import ProfileService
from agent_app.domain.enums import AnalysisStatus
from agent_app.domain.llm_schemas import LlmClient
from agent_app.domain.schemas import AnalysisView, ProfileUpdate
from agent_app.infrastructure.llm import ModelCallError
from agent_app.infrastructure.repositories import (
    AnalysisRepository,
    ProfileRepository,
    SnapshotRepository,
)
from sqlalchemy.orm import Session


TARGET_PROFILE_FIELDS = frozenset(
    {
        "target_roles",
        "target_directions",
        "desired_work",
        "focus_skills",
        "excluded_directions",
    }
)
PROMPT_VERSION = "analysis-v1"


class AnalysisSnapshotNotFound(LookupError):
    pass


def recommendation_for(target_score: int) -> str:
    if target_score < 30:
        return "deselect"
    if target_score < 60:
        return "cautious"
    return "recommend"


class AnalysisService:
    def __init__(self, session: Session, llm_client: LlmClient) -> None:
        self.snapshots = SnapshotRepository(session)
        self.profiles = ProfileRepository(session)
        self.analyses = AnalysisRepository(session)
        self.llm_client = llm_client

    async def analyze_snapshot(
        self,
        snapshot_id: str,
        *,
        analysis_enabled: bool,
    ) -> AnalysisView:
        snapshot = self.snapshots.get(snapshot_id)
        if snapshot is None:
            raise AnalysisSnapshotNotFound(snapshot_id)

        if not analysis_enabled:
            return self._save(
                snapshot,
                status=AnalysisStatus.SKIPPED,
                target_score=None,
                personal_score=None,
                recommendation="not_scored",
                selected_by_default=True,
                approvable=True,
                target_reasons=[],
                personal_matches=[],
                cautions=[],
            )

        profile_record = self.profiles.get_current()
        profile = ProfileUpdate.model_validate(
            {} if profile_record is None else profile_record.payload
        )
        model_profile = ProfileService.model_context(profile)
        target_profile = {
            key: value
            for key, value in model_profile.items()
            if key in TARGET_PROFILE_FIELDS
        }
        personal_profile = {
            key: value
            for key, value in model_profile.items()
            if key not in TARGET_PROFILE_FIELDS
        }
        job = snapshot.payload
        payload = {
            "target_context": {
                "title": job.get("title", ""),
                "description": job.get("description", ""),
                "skills": job.get("skills", []),
                "profile": target_profile,
                "rules": [
                    "Do not use location or required years of experience for target-direction filtering.",
                    "Missing profile facts are unknown, not evidence of inability.",
                ],
            },
            "personal_context": {
                "job": {
                    "title": job.get("title", ""),
                    "description": job.get("description", ""),
                    "skills": job.get("skills", []),
                    "experience": job.get("experience", ""),
                    "degree": job.get("degree", ""),
                },
                "profile": personal_profile,
            },
        }
        try:
            output = await self.llm_client.analyze(payload)
        except ModelCallError:
            return self._save(
                snapshot,
                status=AnalysisStatus.FAILED,
                target_score=None,
                personal_score=None,
                recommendation="analysis_failed",
                selected_by_default=False,
                approvable=False,
                target_reasons=[],
                personal_matches=[],
                cautions=[],
                error_code="model_call_failed",
            )

        recommendation = recommendation_for(output.target_score)
        return self._save(
            snapshot,
            status=AnalysisStatus.COMPLETED,
            target_score=output.target_score,
            personal_score=output.personal_score,
            recommendation=recommendation,
            selected_by_default=output.target_score >= 30,
            approvable=True,
            target_reasons=output.target_reasons,
            personal_matches=output.personal_matches,
            cautions=output.cautions,
        )

    def _save(
        self,
        snapshot,
        *,
        status: AnalysisStatus,
        target_score: int | None,
        personal_score: int | None,
        recommendation: str,
        selected_by_default: bool,
        approvable: bool,
        target_reasons: list[str],
        personal_matches: list[str],
        cautions: list[str],
        error_code: str = "",
    ) -> AnalysisView:
        payload = {
            "target_score": target_score,
            "personal_score": personal_score,
            "overall_score": (
                None
                if target_score is None or personal_score is None
                else round((target_score + personal_score) / 2)
            ),
            "recommendation": recommendation,
            "selected_by_default": selected_by_default,
            "approvable": approvable,
            "target_reasons": target_reasons,
            "personal_matches": personal_matches,
            "cautions": cautions,
            "model": getattr(self.llm_client, "model", ""),
            "prompt_version": PROMPT_VERSION,
            "error_code": error_code,
        }
        record = self.analyses.save(
            batch_id=snapshot.batch_id,
            snapshot_id=snapshot.id,
            status=status.value,
            payload=payload,
        )
        return AnalysisView(
            id=record.id,
            snapshot_id=snapshot.id,
            status=status,
            **payload,
        )
