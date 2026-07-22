from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from agent_app.api.dependencies import get_session, require_browser_token
from agent_app.application.browser_tasks import (
    BrowserTaskConflict,
    BrowserTaskNotFound,
    BrowserTaskService,
)
from agent_app.domain.schemas import (
    BrowserTaskEnvelope,
    BrowserTaskProgress,
    BrowserTaskResolution,
    BrowserTaskResult,
    BrowserTaskWorker,
)


router = APIRouter(
    prefix="/api/v1/browser",
    tags=["browser"],
    dependencies=[Depends(require_browser_token)],
)


def _raise_task_error(error: Exception) -> None:
    if isinstance(error, BrowserTaskNotFound):
        raise HTTPException(status_code=404, detail="Browser task not found") from error
    if isinstance(error, BrowserTaskConflict):
        raise HTTPException(status_code=409, detail=str(error)) from error
    raise error


@router.post("/heartbeat")
def heartbeat() -> dict[str, bool]:
    return {"ok": True}


@router.get("/tasks/next", response_model=BrowserTaskEnvelope)
def take_next_task(
    worker_id: str,
    session: Session = Depends(get_session),
) -> BrowserTaskEnvelope | Response:
    task = BrowserTaskService(session).take(worker_id)
    if task is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return BrowserTaskEnvelope(
        id=task.id,
        type=task.task_type,
        payload=task.payload,
        lease_seconds=30,
    )


@router.post("/tasks/{task_id}/ack")
def acknowledge_task(
    task_id: str,
    payload: BrowserTaskWorker,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    try:
        task = BrowserTaskService(session).ack(task_id, payload.worker_id)
    except (BrowserTaskNotFound, BrowserTaskConflict) as error:
        _raise_task_error(error)
    return {"status": task.status}


@router.post("/tasks/{task_id}/progress")
def report_progress(
    task_id: str,
    payload: BrowserTaskProgress,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    try:
        accepted = BrowserTaskService(session).progress(
            task_id,
            payload.worker_id,
            payload.sequence,
            payload.status,
            payload.detail,
        )
    except (BrowserTaskNotFound, BrowserTaskConflict) as error:
        _raise_task_error(error)
    return {"accepted": accepted}


@router.post("/tasks/{task_id}/result")
def resolve_task(
    task_id: str,
    payload: BrowserTaskResolution,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    try:
        task = BrowserTaskService(session).resolve(
            task_id,
            payload.worker_id,
            BrowserTaskResult(**payload.model_dump(exclude={"worker_id"})),
        )
    except (BrowserTaskNotFound, BrowserTaskConflict) as error:
        _raise_task_error(error)
    return {"status": task.status}
