"""Approval-note builder — the flagship SIH26117 deliverable.

Turns extracted findings into a formatted Word approval note with a reference list,
which is exactly the artefact the problem statement asks the workbench to produce.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sovereign_workbench.core.deliverables.docx import write_docx


def build_approval_note(
    destination: Path,
    *,
    subject: str,
    findings: list[str],
    recommendation: str,
    references: list[str] | None = None,
    prepared_by: str = "Sovereign Workbench",
) -> Path:
    today = datetime.now(UTC).strftime("%d %b %Y")
    paragraphs = [
        f"Date: {today}",
        f"Prepared by: {prepared_by}",
        "",
        "1. Subject",
        subject,
        "",
        "2. Findings",
    ]
    paragraphs.extend(f"   {i}. {finding}" for i, finding in enumerate(findings, start=1))
    paragraphs.extend(["", "3. Recommendation", recommendation])
    return write_docx(
        destination, title="Approval Note", paragraphs=paragraphs, citations=references
    )
