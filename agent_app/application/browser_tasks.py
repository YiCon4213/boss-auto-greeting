from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agent_app.domain.enums import BatchStatus
from agent_app.domain.schemas import BrowserTaskResult, BrowserTaskType
from agent_app.domain.transitions import next_batch_status
from agent_app.infrastructure.models import AuditEvent, Batch, BrowserTask, JobSnapshot
from agent_app.infrastructure.repositories import BrowserTaskRepository


class BrowserTaskNotFound(LookupError):
    pass


class BrowserTaskConflict(RuntimeError):
    pass


class BrowserTaskService:
    def __init__(
        self,
        session: Session,
        *,
        now: Callable[[], datetime] | None = None,
        lease_seconds: int = 30,
    ) -> None:
        self.session = session
        self.repository = BrowserTaskRepository(session)
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.lease_seconds = lease_seconds

    def create(
        self,
        task_type: BrowserTaskType,
        payload: dict[str, object],
        idempotency_key: str,
        batch_id: str | None = None,
    ) -> BrowserTask:
        return self.repository.create(
            task_type, payload, idempotency_key, batch_id=batch_id
        )

    def take(self, worker_id: str) -> BrowserTask | None:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        return self.repository.take(worker_id, self.now(), self.lease_seconds)

    def _owned(self, task_id: str, worker_id: str) -> BrowserTask:
        task = self.repository.get(task_id)
        if task is None:
            raise BrowserTaskNotFound(task_id)
        if task.leased_by != worker_id:
            raise BrowserTaskConflict("task is not leased by the current worker")
        return task

    def ack(self, task_id: str, worker_id: str) -> BrowserTask:
        task = self._owned(task_id, worker_id)
        if task.resolved_at is not None:
            raise BrowserTaskConflict("task is already resolved")
        if task.status not in {"leased", "acked"}:
            raise BrowserTaskConflict("task cannot be acknowledged")
        task.status = "acked"
        task.acked_at = task.acked_at or self.now()
        return self.repository.commit(task)

    def progress(
        self,
        task_id: str,
        worker_id: str,
        sequence: int,
        status: str,
        detail: dict[str, object],
    ) -> bool:
        del status, detail
        task = self._owned(task_id, worker_id)
        if task.resolved_at is not None:
            raise BrowserTaskConflict("task is already resolved")
        if sequence <= task.progress_sequence:
            return False
        task.progress_sequence = sequence
        self.repository.commit(task)
        return True

    def _apply_collection_result(
        self,
        task: BrowserTask,
        terminal: dict[str, object],
    ) -> None:
        batch = self.session.get(Batch, task.batch_id)
        if batch is None:
            raise BrowserTaskConflict("collection batch no longer exists")
        if BatchStatus(batch.status) is not BatchStatus.COLLECTING:
            raise BrowserTaskConflict("collection batch is not collecting")
        snapshot_count = int(
            self.session.scalar(
                select(func.count(JobSnapshot.id)).where(
                    JobSnapshot.batch_id == batch.id
                )
            )
            or 0
        )
        result_payload = terminal.get("result") or {}
        if not isinstance(result_payload, dict):
            raise BrowserTaskConflict("collection result payload is invalid")
        if terminal.get("ok") is True:
            reported_count = result_payload.get("collected_count")
            if not isinstance(reported_count, int) or reported_count != snapshot_count:
                raise BrowserTaskConflict("collection result does not match snapshot count")
            if snapshot_count > batch.limit:
                raise BrowserTaskConflict("collection result exceeds batch limit")
            batch.status = next_batch_status(
                BatchStatus(batch.status), "collection_complete"
            ).value
            event_type = "collection_completed"
        else:
            event = (
                "security_pause"
                if terminal.get("error_code") == "paused_security"
                else "fail"
            )
            batch.status = next_batch_status(BatchStatus(batch.status), event).value
            event_type = (
                "collection_paused_security"
                if event == "security_pause"
                else "collection_failed"
            )
        counts = dict(batch.counts or {})
        counts["snapshots"] = snapshot_count
        batch.counts = counts
        self.session.add(
            AuditEvent(
                batch_id=batch.id,
                event_type=event_type,
                payload={
                    "task_id": task.id,
                    "snapshot_count": snapshot_count,
                    "error_code": str(terminal.get("error_code") or ""),
                },
            )
        )

    def resolve(
        self,
        task_id: str,
        worker_id: str,
        result: BrowserTaskResult,
    ) -> BrowserTask:
        task = self.repository.get(task_id)
        if task is None:
            raise BrowserTaskNotFound(task_id)
        terminal = result.model_dump()
        if task.resolved_at is not None:
            if task.result == terminal:
                return task
            raise BrowserTaskConflict("a different terminal result already exists")
        if task.leased_by != worker_id:
            raise BrowserTaskConflict("task is not leased by the current worker")
        if task.task_type == "collect_batch":
            self._apply_collection_result(task, terminal)
        task.status = "resolved"
        task.result = terminal
        task.resolved_at = self.now()
        task.lease_expires_at = None
        return self.repository.commit(task)
