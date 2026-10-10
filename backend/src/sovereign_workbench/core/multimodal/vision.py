"""Local vision: describe a scanned document or drawing with a local VLM."""

from __future__ import annotations

import base64
from pathlib import Path

from sovereign_workbench.core.llm.inference import run_chat
from sovereign_workbench.core.llm.provider import ChatMessage
from sovereign_workbench.core.llm.registry import get_registry
from sovereign_workbench.core.llm.router import NoModelAvailable, get_router
from sovereign_workbench.observability.logging import get_logger

log = get_logger(__name__)

_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def to_data_url(path: Path) -> str:
    mime = _MIME.get(path.suffix.lower(), "image/png")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


async def describe_image(path: Path, question: str) -> str:
    try:
        decision = get_router().route(question, has_image=True)
    except NoModelAvailable:
        log.info("no vision model available")
        return ""
    message = ChatMessage("user", question, images=[to_data_url(path)])
    try:
        completion = await run_chat(
            get_registry(), decision.spec, [message], temperature=0.2, max_tokens=768
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("vision model failed", extra={"extra_fields": {"error": str(exc)}})
        return ""
    return completion.text.strip()
