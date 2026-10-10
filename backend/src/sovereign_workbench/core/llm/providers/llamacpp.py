"""llama.cpp server adapter.

The llama.cpp server exposes an OpenAI-compatible API, so this is a thin alias with a
different default base URL.
"""

from __future__ import annotations

from sovereign_workbench.core.llm.providers.openai_compatible import OpenAICompatibleProvider


class LlamaCppProvider(OpenAICompatibleProvider):
    def __init__(self, base_url: str, *, timeout: float = 120.0) -> None:
        super().__init__("llamacpp", base_url, timeout=timeout)
