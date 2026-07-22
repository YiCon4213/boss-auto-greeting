import pytest

from agent_app.application.profiles import ProfileService
from agent_app.domain.llm_schemas import AnalysisModelOutput, GreetingModelOutput
from agent_app.domain.schemas import ProfileUpdate


def test_profile_payload_omits_empty_and_private_fields():
    profile = ProfileUpdate(
        education=[{"school": "华南农业大学", "degree": "研究生"}],
        skills=["Python", "AI Agent"],
        availability={"internship_months": "3-6"},
        strengths=[],
        phone="13800000000",
        email="private@example.com",
        address="private",
    )

    assert ProfileService.model_context(profile) == {
        "education": [{"school": "华南农业大学", "degree": "研究生"}],
        "skills": ["Python", "AI Agent"],
        "availability": {"internship_months": "3-6"},
    }


def test_analysis_output_rejects_scores_outside_zero_to_one_hundred():
    valid = {
        "target_score": 80,
        "personal_score": 60,
        "target_reasons": ["方向匹配"],
        "personal_matches": ["Python"],
        "cautions": [],
    }

    assert AnalysisModelOutput.model_validate(valid).target_score == 80

    with pytest.raises(ValueError):
        AnalysisModelOutput.model_validate({**valid, "target_score": 101})


def test_greeting_output_enforces_text_length():
    output = GreetingModelOutput.model_validate(
        {
            "greeting": "老师您好，我的 Python 和 Agent 项目经验与岗位要求很匹配，期待进一步沟通。",
            "used_facts": ["Python"],
        }
    )
    assert output.used_facts == ["Python"]

    with pytest.raises(ValueError):
        GreetingModelOutput.model_validate({"greeting": "太短", "used_facts": []})
