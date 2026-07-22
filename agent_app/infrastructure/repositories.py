from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from agent_app.domain.enums import BatchStatus
from agent_app.domain.schemas import BatchCreate
from agent_app.infrastructure.models import Batch, BrowserTask, ModelConfig, Profile


class ProfileRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_current(self) -> Profile | None:
        statement = (
            select(Profile)
            .where(Profile.is_current.is_(True))
            .order_by(Profile.version.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def save(self, payload: dict) -> Profile:
        current = self.get_current()
        version = 1 if current is None else current.version + 1
        if current is not None:
            self.session.execute(
                update(Profile)
                .where(Profile.is_current.is_(True))
                .values(is_current=False)
            )
        record = Profile(version=version, payload=payload, is_current=True)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record


class ModelConfigRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_current(self) -> ModelConfig | None:
        statement = (
            select(ModelConfig)
            .where(ModelConfig.is_current.is_(True))
            .order_by(ModelConfig.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def save(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: int,
        temperature: float,
        api_key_ref: str | None,
    ) -> ModelConfig:
        self.session.execute(
            update(ModelConfig)
            .where(ModelConfig.is_current.is_(True))
            .values(is_current=False)
        )
        record = ModelConfig(
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
            api_key_ref=api_key_ref,
            is_current=True,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record


class BatchRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, payload: BatchCreate) -> Batch:
        record = Batch(
            status=BatchStatus.DRAFT.value,
            limit=payload.limit,
            analysis_enabled=payload.analysis_enabled,
            greeting_enabled=payload.greeting_enabled,
            source_url=str(payload.source_url),
            counts={},
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get(self, batch_id: str) -> Batch | None:
        return self.session.get(Batch, batch_id)

    def set_status(self, record: Batch, status: BatchStatus) -> Batch:
        record.status = status.value
        self.session.commit()
        self.session.refresh(record)
        return record


class BrowserTaskRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, task_id: str) -> BrowserTask | None:
        return self.session.get(BrowserTask, task_id)

    def get_by_idempotency_key(self, key: str) -> BrowserTask | None:
        return self.session.scalar(
            select(BrowserTask).where(BrowserTask.idempotency_key == key)
        )

    def create(
        self,
        task_type: str,
        payload: dict[str, object],
        idempotency_key: str,
        batch_id: str | None = None,
    ) -> BrowserTask:
        existing = self.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing
        record = BrowserTask(
            batch_id=batch_id,
            task_type=task_type,
            status="pending",
            idempotency_key=idempotency_key,
            payload=payload,
            attempt_count=0,
            progress_sequence=-1,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def take(
        self,
        worker_id: str,
        now: datetime,
        lease_seconds: int,
    ) -> BrowserTask | None:
        available = or_(
            BrowserTask.status == "pending",
            and_(
                BrowserTask.status.in_(["leased", "acked"]),
                BrowserTask.lease_expires_at < now,
            ),
        )
        for _ in range(3):
            candidate = self.session.scalar(
                select(BrowserTask.id)
                .where(available)
                .order_by(BrowserTask.created_at, BrowserTask.id)
                .limit(1)
            )
            if candidate is None:
                return None
            result = self.session.execute(
                update(BrowserTask)
                .where(BrowserTask.id == candidate, available)
                .values(
                    status="leased",
                    leased_by=worker_id,
                    lease_expires_at=now + timedelta(seconds=lease_seconds),
                    attempt_count=BrowserTask.attempt_count + 1,
                    acked_at=None,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount == 1:
                self.session.commit()
                record = self.get(candidate)
                if record is not None:
                    self.session.refresh(record)
                return record
            self.session.rollback()
        return None

    def commit(self, record: BrowserTask) -> BrowserTask:
        self.session.commit()
        self.session.refresh(record)
        return record
