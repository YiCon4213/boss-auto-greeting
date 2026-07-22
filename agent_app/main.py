from contextlib import asynccontextmanager
from secrets import token_urlsafe

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session, sessionmaker

from agent_app.api.dependencies import require_app_token
from agent_app.api.routers import (
    analysis,
    approvals,
    batches,
    browser,
    profiles,
    settings as settings_router,
    snapshots,
)
from agent_app.config import Settings
from agent_app.domain.llm_schemas import LlmClient
from agent_app.infrastructure.database import create_engine_and_session
from agent_app.infrastructure.secrets import SecretStore, create_secret_store


def create_app(
    settings: Settings | None = None,
    secret_store: SecretStore | None = None,
    session_factory: sessionmaker[Session] | None = None,
    llm_client: LlmClient | None = None,
) -> FastAPI:
    resolved = settings or Settings()
    resolved_secret_store = secret_store or create_secret_store(resolved.data_dir)

    def get_or_create_token(name: str) -> str:
        token = resolved_secret_store.get(name)
        if token is None:
            token = token_urlsafe(32)
            resolved_secret_store.set(name, token)
        return token

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved.ensure_directories()
        engine = None
        resolved_session_factory = session_factory
        if resolved_session_factory is None:
            engine, resolved_session_factory = create_engine_and_session(resolved)
        app.state.settings = resolved
        app.state.secret_store = resolved_secret_store
        app.state.session_factory = resolved_session_factory
        app.state.app_token = get_or_create_token("app_token")
        app.state.browser_token = get_or_create_token("browser_token")
        app.state.llm_client = llm_client
        yield
        if engine is not None:
            engine.dispose()

    app = FastAPI(
        title="BOSS Resume Delivery Agent",
        version=resolved.version,
        lifespan=lifespan,
    )
    app.include_router(batches.router)
    app.include_router(browser.router)
    app.include_router(snapshots.router)
    app.include_router(profiles.router)
    app.include_router(settings_router.router)
    app.include_router(analysis.router)
    app.include_router(approvals.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "boss-resume-delivery-agent",
            "version": resolved.version,
        }

    @app.get("/api/v1/auth-check", dependencies=[Depends(require_app_token)])
    def auth_check() -> dict[str, bool]:
        return {"ok": True}

    return app


app = create_app()
