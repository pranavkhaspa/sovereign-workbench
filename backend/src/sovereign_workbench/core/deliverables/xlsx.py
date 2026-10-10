"""Excel writer (computed spreadsheets)."""

from __future__ import annotations

from pathlib import Path

from sovereign_workbench.observability.logging import get_logger

log = get_logger(__name__)


def write_xlsx(
    destination: Path,
    *,
    sheet_name: str = "Sheet1",
    rows: list[list[object]],
) -> Path:
    from openpyxl import Workbook  # lazy

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    for row in rows:
        sheet.append(list(row))
    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(str(destination))
    log.info("wrote xlsx", extra={"extra_fields": {"path": str(destination)}})
    return destination
