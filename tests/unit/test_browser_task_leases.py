from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent_app.application.browser_tasks import BrowserTaskConflict, BrowserTaskService
from agent_app.domain.schemas import BrowserTaskResult
from agent_app.infrastructure.models import Base


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 22, 8, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> None:
        self.value += delta


@pytest.fixture
def browser_task_service():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    clock = MutableClock()
    try:
        yield BrowserTaskService(session, now=clock), clock
    finally:
        session.close()
        engine.dispose()


def test_expired_browser_task_can_be_released(browser_task_service):
    service, clock = browser_task_service
    task = service.create(
        task_type="collect_batch",
        payload={"batch_id": "batch-1", "limit": 10},
        idempotency_key="collect:batch-1",
    )
    leased = service.take("worker-1")
    assert leased is not None
    assert leased.id == task.id
    clock.advance(timedelta(seconds=31))
    released = service.take("worker-2")
    assert released is not None
    assert released.id == task.id
    assert released.attempt_count == 2


def test_duplicate_idempotency_key_returns_existing_task(browser_task_service):
    service, _ = browser_task_service
    first = service.create("pause", {}, "pause:batch-1")
    second = service.create("pause", {}, "pause:batch-1")
    assert second.id == first.id


def test_only_current_worker_can_ack_and_report_progress(browser_task_service):
    service, _ = browser_task_service
    task = service.create("pause", {}, "pause:batch-2")
    service.take("worker-1")
    with pytest.raises(BrowserTaskConflict, match="current worker"):
        service.ack(task.id, "worker-2")
    service.ack(task.id, "worker-1")
    assert service.progress(task.id, "worker-1", 2, "running", {}) is True
    assert service.progress(task.id, "worker-1", 2, "duplicate", {}) is False
    assert service.progress(task.id, "worker-1", 1, "older", {}) is False


def test_first_terminal_result_wins_idempotently(browser_task_service):
    service, _ = browser_task_service
    task = service.create("pause", {}, "pause:batch-3")
    service.take("worker-1")
    first = BrowserTaskResult(ok=True, result={"paused": True})
    resolved = service.resolve(task.id, "worker-1", first)
    repeated = service.resolve(task.id, "worker-1", first)
    assert resolved.result == repeated.result == first.model_dump()
    with pytest.raises(BrowserTaskConflict, match="terminal result"):
        service.resolve(
            task.id,
            "worker-1",
            BrowserTaskResult(ok=False, error_code="different"),
        )
