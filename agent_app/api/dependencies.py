import hmac
from collections.abc import Iterator
from typing import Annotated

from fastapi import Header, HTTPException, Request, status
from sqlalchemy.orm import Session


def _require_token(request: Request, provided: str | None, state_name: str) -> None:
    expected = getattr(request.app.state, state_name, None)
    if (
        provided is None
        or not isinstance(expected, str)
        or not hmac.compare_digest(provided, expected)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing agent token",
        )


def require_app_token(
    request: Request,
    x_agent_token: Annotated[str | None, Header(alias="X-Agent-Token")] = None,
) -> None:
    _require_token(request, x_agent_token, "app_token")


def require_browser_token(
    request: Request,
    x_agent_token: Annotated[str | None, Header(alias="X-Agent-Token")] = None,
) -> None:
    _require_token(request, x_agent_token, "browser_token")


def get_session(request: Request) -> Iterator[Session]:
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        yield session
