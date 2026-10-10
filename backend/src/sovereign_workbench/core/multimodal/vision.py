"""Local vision: describe a scanned document or drawing with a local VLM."""

from __future__ import annotations

import asyncio
import base64
from io import BytesIO
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


def _image_urls(path: Path) -> list[str]:
    if path.suffix.lower() != ".pdf":
        return [to_data_url(path)]
    from pdf2image import convert_from_path

    images = convert_from_path(path, dpi=120, first_page=1, last_page=3, timeout=60)
    try:
        urls = []
        for image in images:
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            urls.append("data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode())
        return urls
    finally:
        for image in images:
            image.close()


async def describe_image(path: Path, question: str) -> str:
    try:
        decision = get_router().route(question, has_image=True)
    except NoModelAvailable:
        log.info("no vision model available")
        return ""
    try:
        message = ChatMessage("user", question, images=await asyncio.to_thread(_image_urls, path))
        completion = await run_chat(
            get_registry(), decision.spec, [message], temperature=0.2, max_tokens=768
        )
    except Exception as exc:
        log.warning("vision model failed", extra={"extra_fields": {"error": str(exc)}})
        return ""
    return completion.text.strip()
