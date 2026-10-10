"""Deterministic approval-note generation from local report sources."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from sovereign_workbench.core.agent.tools.base import Tool, ToolContext, ToolResult
from sovereign_workbench.core.agent.tools.fs_tools import _safe_path
from sovereign_workbench.core.deliverables.reports import build_approval_note
from sovereign_workbench.core.rag.extract import extract_pages


class CreateApprovalNoteArgs(BaseModel):
    source_paths: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Report or scan paths relative to the task workspace.",
    )
    subject: str = Field(
        default="Inspection report findings and approval request",
        min_length=1,
        max_length=240,
    )
    findings: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Optional verbatim findings found in the source text.",
    )
    recommendation: str = Field(
        default=(
            "Approve the recommended corrective action after the responsible engineering, "
            "safety and maintenance reviews are complete."
        ),
        min_length=1,
        max_length=2_000,
    )


class CreateApprovalNoteTool(Tool):
    name = "create_approval_note"
    description = (
        "Extract findings from local inspection reports or scanned documents using local "
        "text extraction/OCR and write a downloadable approval-note DOCX. The generated "
        "document stays inside the task artifact flow."
    )
    args_schema = CreateApprovalNoteArgs

    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(args, CreateApprovalNoteArgs)
        source_paths = args.source_paths or _workspace_sources(ctx.workspace_dir)
        if not source_paths:
            return ToolResult(
                ok=False,
                error="no source documents were supplied",
                data={"failure_code": "NO_SOURCE_DOCUMENT"},
            )

        extracted: list[str] = []
        source_texts: list[str] = []
        references: list[str] = []
        failed_sources: list[str] = []
        for relative_path in source_paths:
            try:
                source = _safe_path(ctx, relative_path)
            except ValueError as exc:
                return ToolResult(
                    ok=False,
                    error=str(exc),
                    data={"failure_code": "SOURCE_PATH_INVALID"},
                )
            if not source.is_file():
                failed_sources.append(relative_path)
                continue
            try:
                pages = extract_pages(source)
            except Exception as exc:
                failed_sources.append(f"{relative_path}: {exc}")
                continue
            source_text = "\n".join(text for _, text in pages if text.strip()).strip()
            if source_text:
                extracted.extend(_finding_candidates(source_text))
                source_texts.append(source_text)
                references.append(source.name)
            else:
                failed_sources.append(relative_path)

        findings = _dedupe(extracted)
        if not findings:
            detail = "OCR/text extraction returned no readable findings"
            if failed_sources:
                detail += f" for: {', '.join(failed_sources[:4])}"
            return ToolResult(
                ok=False,
                error=detail,
                data={
                    "failure_code": "OCR_NO_TEXT",
                    "sources": source_paths,
                    "failed_sources": failed_sources,
                },
            )
        if failed_sources:
            return ToolResult(
                ok=False,
                error=f"some attached sources were unreadable: {', '.join(failed_sources[:4])}",
                data={"failure_code": "OCR_INCOMPLETE", "failed_sources": failed_sources},
            )
        verified_findings = [
            finding
            for finding in args.findings
            if any(finding.casefold() in text.casefold() for text in source_texts)
        ]
        findings = _dedupe(verified_findings + findings)

        subject = args.subject
        if subject == CreateApprovalNoteArgs.model_fields["subject"].default:
            prompt = str(ctx.extras.get("prompt", "")).strip()
            if prompt:
                subject = prompt[:240]
        destination = ctx.workspace_dir / "approval_note.docx"
        try:
            build_approval_note(
                destination,
                subject=subject,
                findings=findings[:20],
                recommendation=args.recommendation,
                references=references or source_paths,
            )
        except Exception as exc:
            return ToolResult(
                ok=False,
                error=f"could not create DOCX approval note: {exc}",
                data={"failure_code": "DOCX_WRITE_FAILED"},
            )

        return ToolResult(
            ok=True,
            output=(
                f"created approval_note.docx with {len(findings[:20])} findings "
                f"from {len(references)} readable source(s)"
            ),
            data={
                "kind": "docx",
                "findings": findings[:20],
                "sources": source_paths,
            },
            artifact_path=destination,
        )


_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
_SOURCE_SUFFIXES = _IMAGE_SUFFIXES | {".pdf", ".docx", ".txt", ".md", ".markdown"}


def _workspace_sources(workspace: Path) -> list[str]:
    return [
        path.name
        for path in sorted(workspace.iterdir())
        if path.is_file() and path.suffix.lower() in _SOURCE_SUFFIXES
    ][:8]


def _finding_candidates(text: str) -> list[str]:
    lines = [re.sub(r"^[\s\-•*\d.)]+", "", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if len(line) >= 8]
    if len(lines) <= 1:
        lines = re.split(r"(?<=[.!?])\s+", " ".join(lines))
    return [line[:1_000] for line in lines if line.strip()]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = " ".join(value.split())
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result
