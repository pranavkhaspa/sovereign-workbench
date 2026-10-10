# ADR 0002 — Local backend runtime and durable task recovery

Date: 2026-10-10

Status: Accepted

## Decisions

- Keep retrieval in SQLite with cosine search and a deterministic hashing embedder by
  default. Optional sentence-transformers is loaded lazily, uses only cached files
  in air-gap mode, and fails explicitly if its configured model cannot load. Chroma
  and reranking are not required for the small-machine implementation.
- Persist every agent event, including tokens, in `task_events`. Start execution on
  the first SSE subscription and retain the worker independently of subscribers.
  Reconnect with `Last-Event-ID` or `?after=`. Run only one task at a time in the
  single-process backend to bound memory. On restart, mark interrupted runs failed;
  never rerun tools with side effects automatically.
- Re-plan once on recoverable tool failure and refresh remaining plans after source
  reads. The configured total step limit applies across all plans. Permission errors
  and unreadable approval-note sources are terminal.
- Use pre-pulled Docker images for strong code isolation when available, with no
  network, read-only mounts/root, non-root user, dropped capabilities and resource
  limits. Subprocess mode remains explicitly best-effort. Neither driver downloads
  dependencies at execution time. Timeout/cancellation cleans up the process group
  and, for Docker, the container.
- Expose DOCX/PPTX/XLSX writers as tools. XLSX formulas have cached computed values
  through a restricted arithmetic evaluator. Unsupported formulas and circular
  references fail rather than silently producing zero. Code execution returns both
  source and a verification log. Artifacts are immutable snapshots.
- Use Apache-2.0 Qwen2.5 1.5B and Qwen2.5-Coder 1.5B weights on the minimum tier;
  keep their existing registry IDs. Use the published `qwen2.5vl:7b` large-tier tag.
- Retain the existing HTTPX transport. Dependency licensing is permissive by default
  with two explicit MPL-2.0 exceptions: unmodified `certifi` (HTTPX's certificate data)
  and development-only `pathspec` (Black). CI separately checks that these two packages
  retain their expected licence; MPL is not globally allowed. Preserve their upstream
  licence files/source notices in redistributed packages. This is not an
  all-permissive transitive dependency claim.
- Tesseract and Poppler are separately installed local OCR programs. Poppler is
  GPL-licensed; container distributions retain the distro's package licence notices.
  It is not linked into the Python application. Distribution must include access to
  the corresponding upstream/distro sources under those packages' terms.

## Consequences

Frontend routes and existing response fields remain compatible; event IDs, citations,
and structured tool-result metadata are additive. Multiple Uvicorn workers are not
supported by the in-process scheduler. Large-corpus ANN retrieval, PaddleOCR, and a
full Excel calculation engine are optional future work.

Tests run with network connections denied, fake LLM responses, real office parsers,
real subprocess execution, and real OCR when the host programs are installed. Live
LLM output quality, Docker isolation and minimum-hardware performance must additionally
be validated on the deployment machine.
