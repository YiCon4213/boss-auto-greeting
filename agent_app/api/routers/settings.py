from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from agent_app.api.dependencies import get_session, require_app_token
from agent_app.domain.schemas import ModelConfigRead, ModelConfigUpdate
from agent_app.infrastructure.repositories import ModelConfigRepository


API_KEY_SECRET_NAME = "openai_api_key"

router = APIRouter(
    prefix="/api/v1/settings",
    tags=["settings"],
    dependencies=[Depends(require_app_token)],
)


def to_response(record, api_key_configured: bool) -> ModelConfigRead:
    return ModelConfigRead(
        base_url=record.base_url,
        model=record.model,
        timeout_seconds=record.timeout_seconds,
        temperature=record.temperature,
        api_key_configured=api_key_configured,
    )


@router.get("/model", response_model=ModelConfigRead)
def get_model_config(
    request: Request,
    session: Session = Depends(get_session),
) -> ModelConfigRead:
    record = ModelConfigRepository(session).get_current()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No model configuration has been saved",
        )
    configured = request.app.state.secret_store.get(API_KEY_SECRET_NAME) is not None
    return to_response(record, configured)


@router.put("/model", response_model=ModelConfigRead)
def put_model_config(
    payload: ModelConfigUpdate,
    request: Request,
    session: Session = Depends(get_session),
) -> ModelConfigRead:
    secret_store = request.app.state.secret_store
    if payload.api_key is not None:
        secret_store.set(API_KEY_SECRET_NAME, payload.api_key.get_secret_value())
    configured = secret_store.get(API_KEY_SECRET_NAME) is not None
    record = ModelConfigRepository(session).save(
        base_url=str(payload.base_url),
        model=payload.model,
        timeout_seconds=payload.timeout_seconds,
        temperature=payload.temperature,
        api_key_ref=API_KEY_SECRET_NAME if configured else None,
    )
    return to_response(record, configured)
