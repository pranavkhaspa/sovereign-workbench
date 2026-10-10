"""Local OCR. Tesseract is the default (no heavy deps, runs on CPU)."""

from __future__ import annotations

from pathlib import Path

from sovereign_workbench.observability.logging import get_logger

log = get_logger(__name__)


def extract_text(path: Path, *, language: str = "eng") -> str:
    if path.suffix.lower() == ".pdf":
        return "\n".join(extract_pdf_pages(path, language=language)).strip()
    try:
        import pytesseract  # lazy
        from PIL import Image  # lazy
    except ImportError:
        log.warning("pytesseract/Pillow not installed; OCR unavailable")
        return _fallback_pdf_text(path)
    try:
        with Image.open(path) as image:
            return pytesseract.image_to_string(image.convert("RGB"), lang=language).strip()
    except Exception as exc:
        log.warning("ocr failed", extra={"extra_fields": {"error": str(exc), "path": str(path)}})
        return _fallback_pdf_text(path)


def _fallback_pdf_text(path: Path) -> str:
    if path.suffix.lower() != ".pdf":
        return ""
    try:
        from pypdf import PdfReader  # lazy

        return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages).strip()
    except Exception:
        return ""


def extract_pdf_pages(
    path: Path, *, language: str = "eng", page_numbers: list[int] | None = None
) -> list[str]:
    """OCR image-only PDFs when the optional local renderer is installed."""
    try:
        import pytesseract  # lazy
        from pdf2image import convert_from_path, pdfinfo_from_path  # lazy
    except ImportError:
        fallback = _fallback_pdf_text(path)
        return [fallback] if fallback else []
    try:
        numbers = page_numbers or list(range(1, int(pdfinfo_from_path(str(path))["Pages"]) + 1))
        pages = []
        for number in numbers:
            images = convert_from_path(
                path, dpi=180, thread_count=1, first_page=number, last_page=number, timeout=60
            )
            try:
                pages.append(
                    "\n".join(
                        pytesseract.image_to_string(image, lang=language, timeout=60).strip()
                        for image in images
                    )
                )
            finally:
                for image in images:
                    image.close()
        return pages
    except Exception as exc:
        log.warning(
            "pdf OCR failed",
            extra={"extra_fields": {"error": str(exc), "path": str(path)}},
        )
        return []
