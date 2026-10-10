# CONTEXT.md — Sovereign Workbench

> Read this file first, every session. It is the single source of truth for **what we
> are building, why, for whom, and how the repo is structured.** If you are an AI
> agent or a new human contributor, this file gives you enough to work without
> asking. When you change a decision here, update `docs/ARCHITECTURE.md` and add an
> ADR in `docs/adr/`.

---

## 1. What this is, in one paragraph

**Sovereign Workbench** is a self-hosted, air-gapped AI workbench for confidential
industrial and government knowledge work. It runs entirely on the organisation's own
hardware — an open-weight LLM plus local tools — so that sensitive documents
(scanned inspection reports, engineering drawings, financials, internal
correspondence) never leave the premises. The user types a task, the agent plans and
executes it with local tools, and returns a **real deliverable** (a Word/PPT/Excel
file, working code, or a calculation with steps shown), not just a chat reply. The
system proves its "sovereignty" by logging every network attempt and showing zero
outbound calls.

## 2. Why it exists (the problem)

Refineries, PSUs, defence-linked manufacturing units and government offices generate a
lot of routine but sensitive knowledge work: approval notes, board presentations,
engineering calculations, internal tooling code, review of scanned drawings and
inspection reports. This work **cannot** go through cloud AI assistants (Claude,
ChatGPT, Codex) because company policy keeps the data on-premises. So staff either do
it manually (slow) or quietly paste confidential material into public tools (a serious
security breach). Nothing deployable exists today that these users can work with the
way they use cloud assistants — but off-premises.

This project is a response to **Smart India Hackathon 2026 problem statement
SIH26117** ("Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal
LLMs for Confidential Industrial Work", Mangalore Refinery and Petrochemicals Limited).

## 3. Who uses it

| Persona | What they do with it |
| --- | --- |
| **Engineer / technician** (refinery, plant, PSU) | Ask it to read a scanned inspection report, extract findings, and draft an approval note as a Word file |
| **Manager / official** | Draft board presentations, summarize correspondence, do spreadsheet analysis |
| **Developer / analyst** | Generate or fix internal tooling code, run it in a sandbox, get results |
| **IT / security admin** | Deploy it, watch the audit log and egress monitor, prove no data left the network |

## 4. What the user gets at the end

Input: a natural-language task + attached files (PDF, image, spreadsheet, drawing).

Output: a **finished artifact**, downloadable from the UI:

- `.docx` approval notes / reports
- `.pptx` presentations
- `.xlsx` spreadsheets with computed cells
- source code that was executed in a sandbox (with stdout/verification)
- numeric calculations with the intermediate steps shown
- a grounded answer with citations back to the organisation's own manuals/SOPs

Plus: a visible **agent timeline** (what it planned, which tools it called) and a
visible **sovereignty panel** (external network calls: 0).

## 5. Hard constraints (this shapes every decision)

1. **Must eventually run on the owner's laptop:** Intel i3 (3rd gen), **8 GB RAM**,
   **2 GB GPU**, no internet dependency. This is the *minimum tier*. Everything must
   work there with small quantized open-weight models.
2. **API keys are a fallback, not the default.** Bigger machines / GPU servers should
   be able to use bigger local models. Cloud APIs (OpenAI/Anthropic/OpenRouter/Gemini)
   exist as an optional provider that is **hard-disabled in air-gap mode**.
3. **Add new models without redesign.** The model layer is a registry + router, not
   hardcoded calls.
4. **Two-person team.** One backend/infra owner, one frontend owner (Rohit). Keep the
   API contract stable so both can work in parallel.
5. **Open source first.** Application dependencies and model weights use permissive
   licences by default. The named unmodified MPL-2.0 exceptions (`certifi`, development
   `pathspec`) and separately packaged OCR executables are recorded in ADR 0002;
   do not claim the entire transitive runtime is permissively licensed.
   No closed SaaS is required for core function.

## 6. Model strategy (see `docs/MODELS.md`)

| Role | Minimum tier (8 GB / 2 GB GPU) | Larger tier |
| --- | --- | --- |
| General / reasoning | Qwen2.5-1.5B-Instruct (Q4_K_M) | Qwen2.5-14B / 32B (Q4) |
| Code | Qwen2.5-Coder-1.5B-Instruct (Q4) | Qwen2.5-Coder-14B/32B |
| Fast / utility | Qwen2.5-1.5B-Instruct (Q4) | Qwen2.5-7B |
| Vision (scanned docs, drawings) | Moondream2 (Q4) or SmolVLM-500M | Qwen2.5-VL-7B |
| Embeddings | bge-small-en-v1.5 (CPU) | bge-large / nomic-embed |
| OCR | Tesseract (default) | PaddleOCR |

Runtime: **Ollama** by default (OpenAI-compatible `/v1`), with `llama.cpp` server and
remote OpenAI-compatible endpoints as alternates. All three speak the same interface
via our provider abstraction.

## 7. High-level architecture (detail in `docs/ARCHITECTURE.md`)

```
 Frontend (React + Vite + TS)
        |  REST + SSE (agent step stream)
        v
 FastAPI backend
   ├── API routes: chat, tasks, documents, models, artifacts, audit, health
   ├── Agent core: planner -> executor -> tool calls -> observer -> loop
   │      └── Tools: fs, code_exec (sandbox), spreadsheet, doc_search, ocr_vision
   ├── LLM layer: provider abstraction + registry + capability router
   ├── RAG: ingest -> chunk -> embed -> vector store -> retrieve (+ citations)
   ├── Multimodal: OCR + local vision model
   ├── Deliverables: docx / pptx / xlsx / code writers
   ├── Security: EgressGuard (air-gap) + AuditLog
   └── Persistence: SQLite (tasks, artifacts, audit) + local vector store
```

**Design rules**

- The agent is an **original, lightweight harness** (plan → act → observe → iterate).
  Do not route every tool call back through the model if it can be deterministic.
- The **model is never imported directly by feature code** — always through the router.
- Tools declare a JSON schema and are registered; the agent discovers them from the
  registry.
- **Fail closed on egress.** In air-gap mode, any attempt to reach a non-local host is
  blocked *and logged*, never silently allowed.
- Heavy optional dependencies (torch, chromadb, paddleocr) are imported **lazily** so
  the core runs on a thin 8 GB box.
- The minimum deployment uses SQLite vector search and hashing embeddings; semantic
  embeddings are an opt-in cached model. Task events are durable and reconnectable;
  the backend runs one active task in one Uvicorn process. See ADR 0002.

## 8. Repository layout

```
sovereign-workbench/
├── CONTEXT.md              <- you are here
├── CHECKLIST.md            <- build plan + Rohit's frontend tasks
├── README.md
├── docs/                   ARCHITECTURE, SOVEREIGNTY, MODELS, adr/
├── backend/                FastAPI + agent core (Python)
│   ├── src/sovereign_workbench/
│   └── tests/
├── frontend/               React + Vite + TS (owner: Rohit)
├── models/models.toml      model registry (edit to add models)
├── scripts/                bootstrap, pull models, dev, verify-airgap
└── .github/workflows/      CI (backend, frontend, docker, codeql, licences)
```

## 9. Definition of done (demo)

Per SIH26117 "Expected Solution", the finished demo must show all of:

1. A task carried **end to end**: read a scanned inspection report → extract findings
   → draft an approval note **as a `.docx`**.
2. A **coding** task run and verified in a **sandbox**.
3. A **multimodal** task (image / scanned document understanding).
4. **Model auto-selection** across at least two task types.
5. **Proof of sovereignty**: logs / network monitor showing **no external calls**.
6. Runs on the **8 GB / i3 / 2 GB GPU** machine with small models.

## 10. Conventions

- **Licence:** Apache-2.0. New files carry no per-file header unless required.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
- **Branches:** `feat/<scope>-<short>`, `fix/<scope>-<short>`. PRs use the template.
- **Backend style:** `ruff` + `black` + `mypy` (strict on `core/`). Type everything
  public. No comments unless they explain *why*.
- **Frontend style:** TypeScript strict, `eslint` + `prettier`, functional components,
  no `any`.
- **Never commit secrets.** All config via env / `.env` (git-ignored).
- **No network in tests.** CI must pass with egress blocked.
