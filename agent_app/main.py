from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent_app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved.ensure_directories()
        app.state.settings = resolved
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

    return app


app = create_app()
