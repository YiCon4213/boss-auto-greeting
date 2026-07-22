from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agent_app.api.dependencies import get_session, require_browser_token
from agent_app.application.snapshots import (
    SnapshotBatchConflict,
    SnapshotBatchNotFound,
    SnapshotService,
)
from agent_app.domain.schemas import JobSnapshotCreate, JobSnapshotRead


router = APIRouter(
    prefix="/api/v1/browser/batches",
    tags=["browser-snapshots"],
    dependencies=[Depends(require_browser_token)],
)


@router.post("/{batch_id}/snapshots", response_model=JobSnapshotRead)
def create_snapshot(
    batch_id: str,
    payload: JobSnapshotCreate,
    session: Session = Depends(get_session),
) -> JobSnapshotRead:
    try:
        return SnapshotService(session).create(batch_id, payload)
    except SnapshotBatchNotFound as error:
        raise HTTPException(status_code=404, detail="Batch not found") from error
    except SnapshotBatchConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
