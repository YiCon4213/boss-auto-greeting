from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agent_app.api.dependencies import get_session, require_app_token
from agent_app.application.profiles import ProfileService
from agent_app.domain.schemas import ProfileRead, ProfileUpdate
from agent_app.infrastructure.repositories import ProfileRepository


router = APIRouter(
    prefix="/api/v1/profiles",
    tags=["profiles"],
    dependencies=[Depends(require_app_token)],
)


@router.get("/current", response_model=ProfileRead)
def get_current_profile(session: Session = Depends(get_session)) -> ProfileRead:
    profile = ProfileService(ProfileRepository(session)).get_current()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile has been configured",
        )
    return profile


@router.put("/current", response_model=ProfileRead)
def put_current_profile(
    payload: ProfileUpdate,
    session: Session = Depends(get_session),
) -> ProfileRead:
    return ProfileService(ProfileRepository(session)).save(payload)
