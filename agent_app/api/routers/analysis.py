from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from agent_app.api.dependencies import get_session, require_app_token
from agent_app.application.approvals import BatchAnalysisCoordinator
from agent_app.domain.llm_schemas import LlmClient
from agent_app.infrastructure.llm import OpenAICompatibleClient
from agent_app.infrastructure.repositories import BatchRepository, ModelConfigRepository


router = APIRouter(
    prefix="/api/v1/batches",
    tags=["analysis"],
    dependencies=[Depends(require_app_token)],
)


def _resolve_llm(request: Request, session: Session) -> tuple[LlmClient, bool]:
    injected = request.app.state.llm_client
    if injected is not None:
        return injected, False
    config = ModelConfigRepository(session).get_current()
    api_key = request.app.state.secret_store.get("openai_api_key")
    if config is None or not api_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Model configuration and API key are required",
        )
    return (
        OpenAICompatibleClient(
            base_url=config.base_url,
            model=config.model,
            api_key=api_key,
            timeout_seconds=config.timeout_seconds,
            temperature=config.temperature,
        ),
        True,
    )


async def _run_analysis(session_factory, llm_client, owned, batch_id):
    try:
        with session_factory() as session:
            await BatchAnalysisCoordinator(session, llm_client).run(batch_id)
    finally:
        if owned:
            await llm_client.aclose()


@router.post("/{batch_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
def analyze_batch(
    batch_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    batch = BatchRepository(session).get(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.status not in {"collected", "analyzing", "awaiting_approval"}:
        raise HTTPException(status_code=409, detail="Batch cannot be analyzed")
    if batch.status == "collected":
        llm_client, owned = _resolve_llm(request, session)
        background_tasks.add_task(
            _run_analysis,
            request.app.state.session_factory,
            llm_client,
            owned,
            batch_id,
        )
    return {"batch_id": batch_id, "status": batch.status}
