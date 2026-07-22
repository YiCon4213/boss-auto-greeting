import re
from collections.abc import Iterable

from sqlalchemy.orm import Session

from agent_app.application.profiles import ProfileService
from agent_app.domain.llm_schemas import LlmClient
from agent_app.domain.schemas import GreetingView, ProfileUpdate
from agent_app.infrastructure.llm import ModelCallError
from agent_app.infrastructure.repositories import (
    AnalysisRepository,
    BatchRepository,
    GreetingRepository,
    ProfileRepository,
    SnapshotRepository,
)


BASE_GREETING = (
    "老师您好，我是来自华南农业大学（双一流）的研究生。仔细阅读贵公司的招聘要求，"
    "我认为自己能够胜任这份工作。本人具备AI Agent 和后端开发等技术栈和项目实践经历。"
    "在Github上有多个开源项目。此外还拥有丰富的科研，竞赛和工作经历，科研课题与机器学习，"
    "自然语言识别相关。可实习3个月至6个月，面试通过可3日内到岗"
)


class GreetingSnapshotNotFound(LookupError):
    pass


def _facts(value: object) -> Iterable[str]:
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            yield normalized
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _facts(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _facts(nested)


def _redact_sensitive(text: str, profile: ProfileUpdate) -> str:
    redacted = text
    for field_name in ProfileService.sensitive_fields:
        value = getattr(profile, field_name)
        if value:
            redacted = redacted.replace(value, "")
    redacted = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "", redacted)
    redacted = re.sub(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "", redacted
    )
    return re.sub(r"[，,]{2,}", "，", redacted).strip(" ，,")


class GreetingService:
    def __init__(self, session: Session, llm_client: LlmClient) -> None:
        self.snapshots = SnapshotRepository(session)
        self.batches = BatchRepository(session)
        self.profiles = ProfileRepository(session)
        self.analyses = AnalysisRepository(session)
        self.greetings = GreetingRepository(session)
        self.llm_client = llm_client

    async def generate(self, snapshot_id: str) -> GreetingView:
        snapshot = self.snapshots.get(snapshot_id)
        if snapshot is None:
            raise GreetingSnapshotNotFound(snapshot_id)
        batch = self.batches.get(snapshot.batch_id)
        if batch is None:
            raise GreetingSnapshotNotFound(snapshot_id)
        profile_record = self.profiles.get_current()
        profile = ProfileUpdate.model_validate(
            {} if profile_record is None else profile_record.payload
        )
        model_profile = ProfileService.model_context(profile)

        if not batch.greeting_enabled:
            return self._save(
                snapshot,
                status="completed",
                source="base_template",
                generated_text=BASE_GREETING,
                final_text=BASE_GREETING,
                used_facts=[],
                approvable=True,
            )

        analysis = self.analyses.get_latest(snapshot_id)
        payload = {
            "base_greeting": BASE_GREETING,
            "job": {
                key: snapshot.payload.get(key)
                for key in ("title", "company", "description", "skills")
            },
            "profile": model_profile,
            "analysis": {} if analysis is None else analysis.payload,
            "rules": [
                "Keep the greeting natural, direct, polite, and concise.",
                "Use only facts present in the provided profile.",
                "Prefer one or two verified skill, availability, or experience matches.",
            ],
        }
        try:
            output = await self.llm_client.generate_greeting(payload)
        except ModelCallError:
            return self._failure(snapshot, "model_call_failed")

        allowed_facts = set(_facts(model_profile))
        if any(fact not in allowed_facts for fact in output.used_facts):
            return self._failure(
                snapshot,
                "unverified_profile_fact",
                generated_text=output.greeting,
                used_facts=output.used_facts,
            )

        text = _redact_sensitive(output.greeting, profile)
        if not 20 <= len(text) <= 500:
            return self._failure(snapshot, "invalid_greeting_length")
        return self._save(
            snapshot,
            status="completed",
            source="model",
            generated_text=text,
            final_text=text,
            used_facts=output.used_facts,
            approvable=True,
        )

    def _failure(
        self,
        snapshot,
        error_code: str,
        *,
        generated_text: str | None = None,
        used_facts: list[str] | None = None,
    ) -> GreetingView:
        return self._save(
            snapshot,
            status="generation_failed",
            source="model",
            generated_text=generated_text,
            final_text=None,
            used_facts=used_facts or [],
            approvable=False,
            error_code=error_code,
        )

    def _save(
        self,
        snapshot,
        *,
        status: str,
        source: str,
        generated_text: str | None,
        final_text: str | None,
        used_facts: list[str],
        approvable: bool,
        error_code: str = "",
    ) -> GreetingView:
        payload = {
            "status": status,
            "source": source,
            "used_facts": used_facts,
            "approvable": approvable,
            "error_code": error_code,
            "model": getattr(self.llm_client, "model", ""),
            "approved_at": None,
        }
        record = self.greetings.save(
            batch_id=snapshot.batch_id,
            snapshot_id=snapshot.id,
            generated_text=generated_text,
            final_text=final_text,
            payload=payload,
        )
        return GreetingView(
            id=record.id,
            snapshot_id=snapshot.id,
            text=final_text or "",
            generated_text=generated_text,
            final_text=final_text,
            **payload,
        )
