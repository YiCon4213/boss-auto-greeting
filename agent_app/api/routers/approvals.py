from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agent_app.api.dependencies import get_session, require_app_token
from agent_app.application.approvals import (
    ApprovalBatchNotFound,
    ApprovalConflict,
    ApprovalService,
)


class DraftUpdate(BaseModel):
    selected: bool
    greeting: str = Field(default="", max_length=500)


class ApprovalItem(BaseModel):
    snapshot_id: str = Field(min_length=32, max_length=32)
    selected: bool
    greeting: str = Field(default="", max_length=500)


class ApprovalRequest(BaseModel):
    items: list[ApprovalItem]


router = APIRouter(
    prefix="/api/v1/batches",
    tags=["approvals"],
    dependencies=[Depends(require_app_token)],
)


def _translate(error: Exception) -> HTTPException:
    if isinstance(error, ApprovalBatchNotFound):
        return HTTPException(status_code=404, detail="Batch or snapshot not found")
    return HTTPException(status_code=409, detail=str(error))


@router.get("/{batch_id}/review")
def review_batch(
    batch_id: str, session: Session = Depends(get_session)
) -> dict[str, object]:
    try:
        return ApprovalService(session).review(batch_id)
    except (ApprovalBatchNotFound, ApprovalConflict) as error:
        raise _translate(error) from error


@router.patch("/{batch_id}/drafts/{snapshot_id}")
def update_draft(
    batch_id: str,
    snapshot_id: str,
    payload: DraftUpdate,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    try:
        return ApprovalService(session).edit_draft(
            batch_id,
            snapshot_id,
            selected=payload.selected,
            greeting=payload.greeting,
        )
    except (ApprovalBatchNotFound, ApprovalConflict) as error:
        raise _translate(error) from error


@router.post("/{batch_id}/approve")
def approve_batch(
    batch_id: str,
    payload: ApprovalRequest,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    try:
        return ApprovalService(session).approve(
            batch_id, [item.model_dump() for item in payload.items]
        )
    except (ApprovalBatchNotFound, ApprovalConflict) as error:
        raise _translate(error) from error
