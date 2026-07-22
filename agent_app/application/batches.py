from agent_app.domain.enums import BatchStatus
from agent_app.domain.schemas import BatchCreate, BatchRead
from agent_app.domain.transitions import available_batch_actions, next_batch_status
from agent_app.infrastructure.models import Batch
from agent_app.infrastructure.repositories import BatchRepository


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
