from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agent_app.application.analysis import AnalysisService
from agent_app.application.greetings import GreetingService
from agent_app.domain.enums import BatchStatus, DeliveryStatus
from agent_app.domain.llm_schemas import LlmClient
from agent_app.domain.transitions import next_batch_status
from agent_app.infrastructure.models import (
    ApprovalVersion,
    AuditEvent,
    Batch,
    DeliveryItem,
    Greeting,
    JobSnapshot,
)
from agent_app.infrastructure.repositories import (
    AnalysisRepository,
    BatchRepository,
    GreetingRepository,
)


class ApprovalBatchNotFound(LookupError):
    pass


class ApprovalConflict(RuntimeError):
    pass


class BatchAnalysisCoordinator:
    def __init__(self, session: Session, llm_client: LlmClient) -> None:
        self.session = session
        self.llm_client = llm_client

    async def run(self, batch_id: str) -> None:
        batch = self.session.get(Batch, batch_id)
        if batch is None:
            raise ApprovalBatchNotFound(batch_id)
        status = BatchStatus(batch.status)
        if status is BatchStatus.AWAITING_APPROVAL:
            return
        if status is BatchStatus.COLLECTED:
            batch.status = next_batch_status(status, "start_analysis").value
            self.session.add(
                AuditEvent(
                    batch_id=batch.id,
                    event_type="analysis_started",
                    payload={},
                )
            )
            self.session.commit()
        elif status is not BatchStatus.ANALYZING:
            raise ApprovalConflict("batch cannot be analyzed")

        snapshots = list(
            self.session.scalars(
                select(JobSnapshot)
                .where(JobSnapshot.batch_id == batch.id)
                .order_by(JobSnapshot.created_at, JobSnapshot.id)
            )
        )
        analysis_count = 0
        greeting_count = 0
        for snapshot in snapshots:
            analysis = await AnalysisService(
                self.session, self.llm_client
            ).analyze_snapshot(
                snapshot.id,
                analysis_enabled=batch.analysis_enabled,
            )
            analysis_count += 1
            if analysis.approvable:
                await GreetingService(self.session, self.llm_client).generate(
                    snapshot.id
                )
                greeting_count += 1

        batch = self.session.get(Batch, batch.id)
        batch.status = next_batch_status(
            BatchStatus(batch.status), "analysis_complete"
        ).value
        batch.counts = {
            **(batch.counts or {}),
            "analyses": analysis_count,
            "greetings": greeting_count,
        }
        self.session.add(
            AuditEvent(
                batch_id=batch.id,
                event_type="analysis_completed",
                payload={
                    "analyses": analysis_count,
                    "greetings": greeting_count,
                },
            )
        )
        self.session.commit()


class ApprovalService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.batches = BatchRepository(session)
        self.analyses = AnalysisRepository(session)
        self.greetings = GreetingRepository(session)

    def review(self, batch_id: str) -> dict[str, object]:
        batch = self.batches.get(batch_id)
        if batch is None:
            raise ApprovalBatchNotFound(batch_id)
        snapshots = list(
            self.session.scalars(
                select(JobSnapshot)
                .where(JobSnapshot.batch_id == batch_id)
                .order_by(JobSnapshot.created_at, JobSnapshot.id)
            )
        )
        items = []
        for snapshot in snapshots:
            analysis = self.analyses.get_latest(snapshot.id)
            greeting = self.greetings.get_latest(snapshot.id)
            analysis_payload = {} if analysis is None else analysis.payload
            greeting_payload = {} if greeting is None else greeting.payload
            items.append(
                {
                    "snapshot_id": snapshot.id,
                    "job_identity_key": snapshot.job_identity_key,
                    "jd_fingerprint": snapshot.jd_fingerprint,
                    "snapshot": snapshot.payload,
                    "analysis_status": None if analysis is None else analysis.status,
                    "analysis": analysis_payload,
                    "greeting_status": greeting_payload.get("status"),
                    "greeting": "" if greeting is None else greeting.final_text or "",
                    "selected": greeting_payload.get(
                        "selected",
                        analysis_payload.get("selected_by_default", False),
                    ),
                    "approvable": bool(
                        analysis_payload.get("approvable")
                        and greeting_payload.get("approvable")
                    ),
                }
            )
        return {"batch_id": batch.id, "status": batch.status, "items": items}

    def edit_draft(
        self,
        batch_id: str,
        snapshot_id: str,
        *,
        selected: bool,
        greeting: str,
    ) -> dict[str, object]:
        batch = self.batches.get(batch_id)
        if batch is None:
            raise ApprovalBatchNotFound(batch_id)
        if BatchStatus(batch.status) is not BatchStatus.AWAITING_APPROVAL:
            raise ApprovalConflict("approved or inactive drafts are immutable")
        snapshot = self.session.get(JobSnapshot, snapshot_id)
        if snapshot is None or snapshot.batch_id != batch_id:
            raise ApprovalBatchNotFound(snapshot_id)
        analysis = self.analyses.get_latest(snapshot_id)
        record = self.greetings.get_latest(snapshot_id)
        if selected and (
            analysis is None
            or not analysis.payload.get("approvable")
            or record is None
            or not record.payload.get("approvable")
        ):
            raise ApprovalConflict("failed items cannot be selected")
        normalized = greeting.strip()
        if selected and not 20 <= len(normalized) <= 500:
            raise ApprovalConflict("selected greeting must contain 20 to 500 characters")
        if record is None:
            raise ApprovalConflict("greeting draft is missing")
        record.final_text = normalized or None
        record.payload = {
            **record.payload,
            "selected": selected,
            "source": "edited" if normalized else record.payload.get("source"),
        }
        self.session.commit()
        return {
            "snapshot_id": snapshot_id,
            "selected": selected,
            "greeting": normalized,
        }

    def approve(
        self, batch_id: str, items: list[dict[str, object]]
    ) -> dict[str, object]:
        batch = self.batches.get(batch_id)
        if batch is None:
            raise ApprovalBatchNotFound(batch_id)
        if BatchStatus(batch.status) is BatchStatus.APPROVED:
            existing = self.session.scalar(
                select(ApprovalVersion)
                .where(ApprovalVersion.batch_id == batch_id)
                .order_by(ApprovalVersion.version.desc())
                .limit(1)
            )
            if existing is None:
                raise ApprovalConflict("approved batch has no approval version")
            count = self.session.scalar(
                select(func.count(DeliveryItem.id)).where(
                    DeliveryItem.approval_version_id == existing.id
                )
            )
            return {
                "batch_id": batch_id,
                "approval_version_id": existing.id,
                "delivery_item_count": count or 0,
            }
        if BatchStatus(batch.status) is not BatchStatus.AWAITING_APPROVAL:
            raise ApprovalConflict("batch is not awaiting approval")

        snapshots = {
            snapshot.id: snapshot
            for snapshot in self.session.scalars(
                select(JobSnapshot).where(JobSnapshot.batch_id == batch_id)
            )
        }
        submitted = {str(item["snapshot_id"]): item for item in items}
        if set(submitted) != set(snapshots):
            raise ApprovalConflict("approval must include every batch snapshot")

        frozen: list[tuple[JobSnapshot, Greeting, str]] = []
        decisions = []
        for snapshot_id, snapshot in snapshots.items():
            item = submitted[snapshot_id]
            selected = bool(item.get("selected"))
            greeting_text = str(item.get("greeting") or "").strip()
            analysis = self.analyses.get_latest(snapshot_id)
            greeting = self.greetings.get_latest(snapshot_id)
            if selected:
                if (
                    analysis is None
                    or not analysis.payload.get("approvable")
                    or greeting is None
                    or not greeting.payload.get("approvable")
                ):
                    raise ApprovalConflict("failed items cannot be approved")
                if not 20 <= len(greeting_text) <= 500:
                    raise ApprovalConflict(
                        "selected greeting must contain 20 to 500 characters"
                    )
                frozen.append((snapshot, greeting, greeting_text))
            decisions.append(
                {
                    "snapshot_id": snapshot_id,
                    "selected": selected,
                    "greeting": greeting_text if selected else "",
                }
            )

        approved_at = datetime.now(timezone.utc)
        latest_version = self.session.scalar(
            select(func.max(ApprovalVersion.version)).where(
                ApprovalVersion.batch_id == batch_id
            )
        )
        approval = ApprovalVersion(
            batch_id=batch_id,
            version=(latest_version or 0) + 1,
            approved_at=approved_at,
            payload={"items": decisions},
        )
        self.session.add(approval)
        self.session.flush()
        for order, (snapshot, greeting, final_text) in enumerate(frozen, start=1):
            greeting.final_text = final_text
            greeting.payload = {
                **greeting.payload,
                "source": "edited"
                if final_text != (greeting.generated_text or "")
                else greeting.payload.get("source"),
                "approved_at": approved_at.isoformat(),
                "selected": True,
            }
            self.session.add(
                DeliveryItem(
                    batch_id=batch_id,
                    approval_version_id=approval.id,
                    job_snapshot_id=snapshot.id,
                    status=DeliveryStatus.APPROVED.value,
                    final_greeting=final_text,
                    payload={
                        "job_identity_key": snapshot.job_identity_key,
                        "jd_fingerprint": snapshot.jd_fingerprint,
                        "title": snapshot.payload.get("title", ""),
                        "company": snapshot.payload.get("company", ""),
                        "order": order,
                        "approved_at": approved_at.isoformat(),
                    },
                )
            )
        batch.status = next_batch_status(
            BatchStatus(batch.status), "approve"
        ).value
        self.session.add(
            AuditEvent(
                batch_id=batch_id,
                event_type="batch_approved",
                payload={
                    "approval_version_id": approval.id,
                    "delivery_item_count": len(frozen),
                },
            )
        )
        self.session.commit()
        return {
            "batch_id": batch_id,
            "approval_version_id": approval.id,
            "delivery_item_count": len(frozen),
        }
