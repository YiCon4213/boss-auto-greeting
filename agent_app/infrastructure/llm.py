import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from agent_app.domain.llm_schemas import AnalysisModelOutput, GreetingModelOutput


OutputT = TypeVar("OutputT", bound=BaseModel)


class ModelCallError(RuntimeError):
    """A privacy-safe model failure suitable for persistence and display."""


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        timeout_seconds: int = 30,
        temperature: float = 0.2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self.model = model
        self.temperature = temperature
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def analyze(self, payload: dict[str, object]) -> AnalysisModelOutput:
        return await self._call("analysis", payload, AnalysisModelOutput)

    async def generate_greeting(
        self, payload: dict[str, object]
    ) -> GreetingModelOutput:
        return await self._call("greeting", payload, GreetingModelOutput)

    async def _call(
        self,
        operation: str,
        payload: dict[str, object],
        output_type: type[OutputT],
    ) -> OutputT:
        request_body = {
            "model": self.model,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": f"Return only the structured JSON for {operation}.",
                },
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
        }
        for attempt in range(2):
            try:
                response = await self._client.post(self.endpoint, json=request_body)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return output_type.model_validate(json.loads(content))
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                KeyError,
                IndexError,
                TypeError,
                ValidationError,
            ):
                if attempt == 1:
                    raise ModelCallError(f"{operation} model call failed") from None
        raise AssertionError("unreachable")
