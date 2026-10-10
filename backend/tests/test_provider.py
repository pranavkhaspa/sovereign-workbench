from __future__ import annotations

import json

import httpx
import pytest

from sovereign_workbench.core.llm.provider import ChatMessage, ModelSpec
from sovereign_workbench.core.llm.providers.openai_compatible import OpenAICompatibleProvider
from sovereign_workbench.core.security.airgap import EgressBlocked, get_client


@pytest.mark.asyncio
async def test_openai_protocol_probe_completion_and_stream(monkeypatch):
    seen = []

    def handle(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "local-model"}]})
        body = json.loads(request.content)
        seen.append(body)
        if body["stream"]:
            return httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"Hello"}}]}\n\ndata: [DONE]\n\n'
            )
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hello"}}]})

    monkeypatch.setattr(
        "sovereign_workbench.core.llm.providers.openai_compatible.get_client",
        lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    provider = OpenAICompatibleProvider("test", "http://127.0.0.1/v1")
    spec = ModelSpec("test", "test", False, "min", ["chat"], "local-model")
    messages = [ChatMessage("user", "Describe", images=["data:image/png;base64,AAAA"])]
    assert await provider.is_available()
    assert await provider.available_models() == {"local-model"}
    assert (await provider.chat(spec, messages)).text == "Hello"
    assert [text async for text in provider.stream(spec, messages)] == ["Hello"]
    assert seen[0]["messages"][0]["content"][1]["image_url"]["url"].startswith("data:")


@pytest.mark.asyncio
async def test_guard_blocks_before_transport_even_with_proxy_env(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://example.com:8080")
    async with get_client() as client:
        with pytest.raises(EgressBlocked):
            await client.get("https://example.com/private")


@pytest.mark.asyncio
async def test_truncated_provider_stream_is_not_success(monkeypatch):
    monkeypatch.setattr(
        "sovereign_workbench.core.llm.providers.openai_compatible.get_client",
        lambda **kwargs: httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, text='data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
                )
            )
        ),
    )
    provider = OpenAICompatibleProvider("test", "http://127.0.0.1/v1")
    spec = ModelSpec("test", "test", False, "min", ["chat"], "local-model")
    with pytest.raises(RuntimeError, match="before completion"):
        async for _ in provider.stream(spec, [ChatMessage("user", "hello")]):
            pass
