"""OpenAI-compatible chat provider.

One adapter covers Ollama (`/v1`), vLLM, llama.cpp server, OpenAI and OpenRouter.
All requests go through :func:`get_client` so the egress guard applies.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from sovereign_workbench.core.llm.provider import ChatMessage, Completion, ModelProvider, ModelSpec
from sovereign_workbench.core.security.airgap import EgressBlocked, get_client
from sovereign_workbench.observability.logging import get_logger

log = get_logger(__name__)


class OpenAICompatibleProvider(ModelProvider):
    def __init__(
        self,
        name: str,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _payload(
        self,
        spec: ModelSpec,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]] | None,
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": spec.model_name,
            "messages": [_to_openai(m) for m in messages],
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
        return payload

    async def is_available(self) -> bool:
        try:
            async with get_client(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/models", headers=self._headers())
                return resp.status_code < 400
        except EgressBlocked:
            return False
        except Exception:
            return False

    async def available_models(self) -> set[str] | None:
        try:
            async with get_client(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/models", headers=self._headers())
                resp.raise_for_status()
                payload = resp.json()
                return {
                    str(entry.get("id") or entry.get("model"))
                    for entry in payload.get("data", [])
                    if entry.get("id") or entry.get("model")
                }
        except Exception:
            return None

    async def chat(
        self,
        spec: ModelSpec,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> Completion:
        payload = self._payload(spec, messages, temperature, max_tokens, tools, stream=False)
        async with get_client(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=self._headers()
            )
            resp.raise_for_status()
            data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return Completion(
            text=message.get("content") or "",
            model_id=spec.id,
            finish_reason=choice.get("finish_reason"),
            usage=data.get("usage") or {},
        )

    async def stream(
        self,
        spec: ModelSpec,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        payload = self._payload(spec, messages, temperature, max_tokens, None, stream=True)
        async with (
            get_client(timeout=self.timeout) as client,
            client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
            ) as resp,
        ):
            resp.raise_for_status()
            finished = False
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                chunk = line.removeprefix("data:").strip()
                if chunk == "[DONE]":
                    finished = True
                    break
                try:
                    choice = json.loads(chunk)["choices"][0]
                    delta = choice["delta"].get("content")
                    finished = finished or choice.get("finish_reason") is not None
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta:
                    yield delta
            if not finished:
                raise RuntimeError("model stream ended before completion")


def _to_openai(message: ChatMessage) -> dict[str, Any]:
    if not message.images:
        payload: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.name:
            payload["name"] = message.name
        return payload
    content: list[dict[str, Any]] = [{"type": "text", "text": message.content}]
    content.extend({"type": "image_url", "image_url": {"url": img}} for img in message.images)
    return {"role": message.role, "content": content}
