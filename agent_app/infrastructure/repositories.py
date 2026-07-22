from sqlalchemy import select, update
from sqlalchemy.orm import Session

from agent_app.domain.enums import BatchStatus
from agent_app.domain.schemas import BatchCreate
from agent_app.infrastructure.models import Batch, ModelConfig, Profile


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
