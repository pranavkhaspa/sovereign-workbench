"""Tools that turn structured agent output into downloadable office files."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sovereign_workbench.core.agent.tools.base import Tool, ToolContext, ToolResult
from sovereign_workbench.core.deliverables.docx import write_docx
from sovereign_workbench.core.deliverables.pptx import write_pptx
from sovereign_workbench.core.deliverables.xlsx import write_xlsx


class CreateDocumentArgs(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    paragraphs: list[str] = Field(max_length=200)
    bullets: list[str] = Field(default_factory=list, max_length=200)
    citations: list[str] = Field(default_factory=list, max_length=100)


class CreateDocumentTool(Tool):
    name = "create_document"
    description = "Write a downloadable Word DOCX report with paragraphs, bullets and references."
    args_schema = CreateDocumentArgs

    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(args, CreateDocumentArgs)
        destination = ctx.workspace_dir / "report.docx"
        write_docx(destination, **args.model_dump())
        return ToolResult(
            ok=True,
            output="created report.docx",
            data={"artifact_kind": "docx"},
            artifact_path=destination,
        )


class SlideArgs(BaseModel):
    title: str = Field(default="", max_length=240)
    body: str = Field(default="", max_length=10_000)


class CreatePresentationArgs(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    slides: list[SlideArgs] = Field(default_factory=list, max_length=40)


class CreatePresentationTool(Tool):
    name = "create_presentation"
    description = "Write a structured PowerPoint presentation into the task artifacts."
    args_schema = CreatePresentationArgs

    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(args, CreatePresentationArgs)
        destination = ctx.workspace_dir / "presentation.pptx"
        try:
            write_pptx(
                destination,
                title=args.title,
                slides=[slide.model_dump() for slide in args.slides],
            )
        except Exception as exc:
            return ToolResult(ok=False, error=f"could not create PPTX: {exc}")
        return ToolResult(
            ok=True,
            output=f"created presentation.pptx with {len(args.slides)} content slides",
            data={"artifact_kind": "pptx"},
            artifact_path=destination,
        )


class CreateSpreadsheetArgs(BaseModel):
    sheet_name: str = Field(default="Sheet1", min_length=1, max_length=31)
    rows: list[list[str | int | float | bool | None]] = Field(
        default_factory=list, max_length=10_000
    )


class CreateSpreadsheetTool(Tool):
    name = "create_spreadsheet"
    description = (
        "Write a downloadable XLSX with cached computed results. Formulas support arithmetic, "
        "cell references/ranges and SUM, AVERAGE, MIN, MAX, ABS."
    )
    args_schema = CreateSpreadsheetArgs

    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(args, CreateSpreadsheetArgs)
        destination = ctx.workspace_dir / "workbook.xlsx"
        try:
            write_xlsx(destination, sheet_name=args.sheet_name, rows=args.rows)
        except Exception as exc:
            return ToolResult(ok=False, error=f"could not create XLSX: {exc}")
        return ToolResult(
            ok=True,
            output=f"created workbook.xlsx with {len(args.rows)} rows",
            data={"artifact_kind": "xlsx", "rows": len(args.rows)},
            artifact_path=destination,
        )
