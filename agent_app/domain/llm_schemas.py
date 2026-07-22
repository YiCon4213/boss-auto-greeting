from typing import Protocol

from pydantic import BaseModel, Field


class AnalysisModelOutput(BaseModel):
    target_score: int = Field(ge=0, le=100)
    personal_score: int = Field(ge=0, le=100)
    target_reasons: list[str] = Field(max_length=5)
    personal_matches: list[str] = Field(max_length=5)
    cautions: list[str] = Field(max_length=5)


class GreetingModelOutput(BaseModel):
    greeting: str = Field(min_length=20, max_length=500)
    used_facts: list[str] = Field(max_length=8)


class LlmClient(Protocol):
    async def analyze(self, payload: dict[str, object]) -> AnalysisModelOutput:
        raise NotImplementedError

    async def generate_greeting(
        self, payload: dict[str, object]
    ) -> GreetingModelOutput:
        raise NotImplementedError
