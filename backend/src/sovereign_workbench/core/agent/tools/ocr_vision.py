"""OCR + local vision tool for scanned documents, drawings and photos."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sovereign_workbench.core.agent.tools.base import Tool, ToolContext, ToolResult
from sovereign_workbench.core.agent.tools.fs_tools import _safe_path


class DescribeImageArgs(BaseModel):
    path: str = Field(description="Image or scanned-document path relative to the workspace.")
    question: str = Field(default="Describe the contents.", description="What to find or explain.")


class DescribeImageTool(Tool):
    name = "describe_image"
    description = (
        "Read a scanned document, handwritten note, engineering drawing or photograph "
        "using local OCR and a local vision model. Returns extracted text and a description."
    )
    args_schema = DescribeImageArgs

    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(args, DescribeImageArgs)
        try:
            target = _safe_path(ctx, args.path)
            if not target.exists():
                return ToolResult(ok=False, error=f"not found: {args.path}")

            from sovereign_workbench.core.multimodal.ocr import extract_text
            from sovereign_workbench.core.multimodal.vision import describe_image

            ocr_text = extract_text(target)
            description = await describe_image(target, args.question)
            output = f"--- OCR text ---\n{ocr_text}\n\n--- vision ---\n{description}"
            return ToolResult(
                ok=True,
                output=output,
                data={"ocr_chars": len(ocr_text), "has_vision": bool(description)},
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, error=str(exc))
