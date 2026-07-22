from hashlib import sha256
import re

from sqlalchemy.orm import Session

from agent_app.domain.enums import BatchStatus
from agent_app.domain.schemas import JobSnapshotCreate, JobSnapshotRead
from agent_app.infrastructure.repositories import BatchRepository, SnapshotRepository


class SnapshotBatchNotFound(LookupError):
    pass


class SnapshotBatchConflict(RuntimeError):
    pass


def make_job_identity_key(
    *, encrypt_job_id: str, security_id: str, lid: str
) -> str:
    parts = [
        ("job", encrypt_job_id.strip()),
        ("security", security_id.strip()),
        ("lid", lid.strip()),
    ]
    reliable = [(name, value) for name, value in parts if value]
    if not reliable:
        raise ValueError("reliable job identity is required")
    return "|".join(f"{name}:{value}" for name, value in reliable)


def make_jd_fingerprint(description: str) -> str:
    normalized = re.sub(r"\s+", " ", description).strip()
    return sha256(normalized.encode("utf-8")).hexdigest()


class SnapshotService:
    def __init__(self, session: Session) -> None:
        self.batches = BatchRepository(session)
        self.snapshots = SnapshotRepository(session)

    def create(self, batch_id: str, payload: JobSnapshotCreate) -> JobSnapshotRead:
        batch = self.batches.get(batch_id)
        if batch is None:
            raise SnapshotBatchNotFound(batch_id)
        if BatchStatus(batch.status) is not BatchStatus.COLLECTING:
            raise SnapshotBatchConflict("batch is not collecting")
        identity_key = make_job_identity_key(
            encrypt_job_id=payload.encrypt_job_id,
            security_id=payload.security_id,
            lid=payload.lid,
        )
        record, duplicate = self.snapshots.create_immutable(
            batch_id=batch_id,
            identity_key=identity_key,
            fingerprint=make_jd_fingerprint(payload.description),
            payload=payload.model_dump(mode="json"),
        )
        return JobSnapshotRead(
            id=record.id,
            batch_id=record.batch_id,
            job_identity_key=record.job_identity_key,
            jd_fingerprint=record.jd_fingerprint,
            payload=record.payload,
            duplicate=duplicate,
        )
