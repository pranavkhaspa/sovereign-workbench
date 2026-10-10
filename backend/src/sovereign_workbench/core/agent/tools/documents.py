"""Read attachment text without asking a text-file tool to decode binary formats."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from sovereign_workbench.core.agent.tools.base import Tool, ToolContext, ToolResult
from sovereign_workbench.core.agent.tools.fs_tools import _safe_path
from sovereign_workbench.core.rag.extract import extract_pages


class ReadDocumentArgs(BaseModel):
    path: str = Field(description="PDF, DOCX, image, spreadsheet or text attachment filename.")


class ReadDocumentTool(Tool):
    name = "read_document"
    description = "Extract local document text, including OCR for scanned PDFs and images."
    args_schema = ReadDocumentArgs

    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(args, ReadDocumentArgs)
        pages = await asyncio.to_thread(extract_pages, _safe_path(ctx, args.path))
        text = "\n\n".join(
            f"[{args.path} p.{page or 1}] {text}" for page, text in pages if text.strip()
        )
        return ToolResult(
            ok=bool(text.strip()),
            output=text[:20_000],
            error=None if text.strip() else "document contains no readable text",
        )
