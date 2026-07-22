from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agent_app.api.dependencies import get_session, require_app_token
from agent_app.application.batches import (
    BatchService,
    CollectionStartConflict,
    CollectionStartNotFound,
    CollectionStartService,
)
from agent_app.domain.schemas import BatchCreate, BatchRead
from agent_app.infrastructure.repositories import BatchRepository


router = APIRouter(
    prefix="/api/v1/batches",
    tags=["batches"],
    dependencies=[Depends(require_app_token)],
)


@router.post("", response_model=BatchRead, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: BatchCreate,
    session: Session = Depends(get_session),
) -> BatchRead:
    return BatchService(BatchRepository(session)).create(payload)


@router.post("/{batch_id}/collect", status_code=status.HTTP_202_ACCEPTED)
def start_collection(
    batch_id: str,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    try:
        return CollectionStartService(session).start(batch_id)
    except CollectionStartNotFound as error:
        raise HTTPException(status_code=404, detail="Batch not found") from error
    except CollectionStartConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{batch_id}", response_model=BatchRead)
def get_batch(
    batch_id: str,
    session: Session = Depends(get_session),
) -> BatchRead:
    batch = BatchService(BatchRepository(session)).get(batch_id)
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    return batch
