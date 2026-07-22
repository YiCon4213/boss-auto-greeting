from agent_app.domain.enums import BatchStatus
from agent_app.domain.schemas import BatchCreate, BatchRead
from agent_app.domain.transitions import available_batch_actions, next_batch_status
from sqlalchemy.orm import Session

from agent_app.infrastructure.models import AuditEvent, Batch
from agent_app.infrastructure.repositories import BatchRepository, BrowserTaskRepository


class CollectionStartNotFound(LookupError):
    pass


class CollectionStartConflict(RuntimeError):
    pass


class CollectionStartService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.batches = BatchRepository(session)
        self.tasks = BrowserTaskRepository(session)

    def start(self, batch_id: str) -> dict[str, str]:
        batch = self.batches.get(batch_id)
        if batch is None:
            raise CollectionStartNotFound(batch_id)
        current = BatchStatus(batch.status)
        if current is BatchStatus.DRAFT:
            batch.status = next_batch_status(current, "start_collection").value
            self.session.add(
                AuditEvent(
                    batch_id=batch.id,
                    event_type="collection_started",
                    payload={"limit": batch.limit},
                )
            )
        elif current is not BatchStatus.COLLECTING:
            raise CollectionStartConflict("batch cannot start collection")
        task = self.tasks.create(
            "collect_batch",
            {
                "batch_id": batch.id,
                "limit": batch.limit,
                "source_url": batch.source_url,
                "expectation_context": {},
            },
            f"collect:{batch.id}",
            batch_id=batch.id,
            commit=False,
        )
        self.session.commit()
        return {"batch_id": batch.id, "task_id": task.id, "status": batch.status}


class BatchService:
    def __init__(self, repository: BatchRepository):
        self.repository = repository

    @staticmethod
    def _to_read(record: Batch) -> BatchRead:
        status = BatchStatus(record.status)
        return BatchRead(
            id=record.id,
            status=status,
            limit=record.limit,
            analysis_enabled=record.analysis_enabled,
            greeting_enabled=record.greeting_enabled,
            source_url=record.source_url,
            counts=record.counts,
            available_actions=available_batch_actions(status),
        )

    def create(self, payload: BatchCreate) -> BatchRead:
        return self._to_read(self.repository.create(payload))

    def get(self, batch_id: str) -> BatchRead | None:
        record = self.repository.get(batch_id)
        return None if record is None else self._to_read(record)

    def transition(self, batch_id: str, event: str) -> BatchRead | None:
        record = self.repository.get(batch_id)
        if record is None:
            return None
        next_status = next_batch_status(BatchStatus(record.status), event)
        return self._to_read(self.repository.set_status(record, next_status))
