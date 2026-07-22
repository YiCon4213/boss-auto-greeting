from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from agent_app.domain.schemas import BrowserTaskResult, BrowserTaskType
from agent_app.infrastructure.models import BrowserTask
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
        task.status = "resolved"
        task.result = terminal
        task.resolved_at = self.now()
        task.lease_expires_at = None
        return self.repository.commit(task)
