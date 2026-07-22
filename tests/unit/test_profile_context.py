from agent_app.application.profiles import ProfileService
from agent_app.domain.schemas import ProfileUpdate


def test_model_context_removes_empty_and_private_fields():
    profile = ProfileUpdate(
        target_roles=["AI 应用工程师"],
        skills=["Python", "FastAPI"],
        email="private@example.com",
        field_visibility={"target_roles": True, "skills": True, "email": False},
    )
    assert ProfileService.model_context(profile) == {
        "target_roles": ["AI 应用工程师"],
        "skills": ["Python", "FastAPI"],
    }
