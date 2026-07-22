import asyncio
import json

import httpx
import pytest

from agent_app.domain.llm_schemas import AnalysisModelOutput, GreetingModelOutput
from agent_app.infrastructure.llm import ModelCallError, OpenAICompatibleClient


ANALYSIS_OUTPUT = {
    "target_score": 75,
    "personal_score": 68,
    "target_reasons": ["目标方向一致"],
    "personal_matches": ["Python"],
    "cautions": ["实习周期需确认"],
}

GREETING_OUTPUT = {
    "greeting": "老师您好，我的 Python 项目经验与岗位要求较为匹配，期待有机会进一步沟通。",
    "used_facts": ["Python"],
}


def completion(content: object) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]},
    )


def run(coroutine):
    return asyncio.run(coroutine)


def test_client_posts_to_chat_completions_with_model_and_bearer_token():
    requests: list[httpx.Request] = []

    async def exercise():
        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return completion(ANALYSIS_OUTPUT)

        client = OpenAICompatibleClient(
            base_url="https://model.example/v1/",
            model="example-model",
            api_key="sk-private",
            transport=httpx.MockTransport(handler),
        )
        try:
            return await client.analyze({"job": {"title": "AI 工程师"}})
        finally:
            await client.aclose()

    result = run(exercise())

    assert isinstance(result, AnalysisModelOutput)
    assert str(requests[0].url) == "https://model.example/v1/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer sk-private"
    body = json.loads(requests[0].content)
    assert body["model"] == "example-model"


def test_client_validates_greeting_output_with_its_own_schema():
    async def exercise():
        async def handler(request: httpx.Request) -> httpx.Response:
            return completion(GREETING_OUTPUT)

        client = OpenAICompatibleClient(
            base_url="https://model.example/v1",
            model="example-model",
            api_key="sk-private",
            transport=httpx.MockTransport(handler),
        )
        try:
            return await client.generate_greeting({"job": {"title": "后端工程师"}})
        finally:
            await client.aclose()

    result = run(exercise())

    assert isinstance(result, GreetingModelOutput)
    assert result.used_facts == ["Python"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not-json"),
        completion({"target_score": 50}),
    ],
)
def test_invalid_response_retries_once_then_raises_safe_error(response):
    attempts = 0

    async def exercise():
        nonlocal attempts

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return response

        client = OpenAICompatibleClient(
            base_url="https://model.example/v1",
            model="example-model",
            api_key="sk-private",
            transport=httpx.MockTransport(handler),
        )
        try:
            await client.analyze({"private": "do-not-leak"})
        finally:
            await client.aclose()

    with pytest.raises(ModelCallError) as exc_info:
        run(exercise())

    assert attempts == 2
    message = str(exc_info.value)
    assert "sk-private" not in message
    assert "do-not-leak" not in message
    assert "not-json" not in message


def test_timeout_retries_once_without_leaking_secret():
    attempts = 0

    async def exercise():
        nonlocal attempts

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            raise httpx.ReadTimeout("request with sk-private timed out", request=request)

        client = OpenAICompatibleClient(
            base_url="https://model.example/v1",
            model="example-model",
            api_key="sk-private",
            transport=httpx.MockTransport(handler),
        )
        try:
            await client.analyze({"private": "do-not-leak"})
        finally:
            await client.aclose()

    with pytest.raises(ModelCallError) as exc_info:
        run(exercise())

    assert attempts == 2
    assert "sk-private" not in str(exc_info.value)
    assert "do-not-leak" not in str(exc_info.value)
