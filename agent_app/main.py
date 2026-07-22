from contextlib import asynccontextmanager
from secrets import token_urlsafe

from fastapi import Depends, FastAPI

from agent_app.api.dependencies import require_app_token
from agent_app.config import Settings
from agent_app.infrastructure.secrets import SecretStore, create_secret_store


def create_app(
    settings: Settings | None = None,
    secret_store: SecretStore | None = None,
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
        app.state.settings = resolved
        app.state.secret_store = resolved_secret_store
        app.state.app_token = get_or_create_token("app_token")
        app.state.browser_token = get_or_create_token("browser_token")
        yield

    app = FastAPI(
        title="BOSS Resume Delivery Agent",
        version=resolved.version,
        lifespan=lifespan,
    )

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
