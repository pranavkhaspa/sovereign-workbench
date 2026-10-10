// Seed dataset for the in-browser mock transport (VITE_USE_MOCK=true).
// It is the single source of truth for mock tasks, artifacts, documents and
// audit rows, so screenshots and frontend-only demos stay reproducible.

import type {
  Artifact,
  AuditEvent,
  Chunk,
  Citation,
  Document,
  EgressStatus,
  HealthStatus,
  ModelInfo,
  Task,
  TaskStep,
} from "../src/api/types";

export interface SeedData {
  health: HealthStatus;
  egress: EgressStatus;
  models: ModelInfo[];
  documents: Document[];
  chunks: Chunk[];
  tasks: Task[];
  artifacts: Artifact[];
  artifactText: Record<string, string>;
  audit: AuditEvent[];
}

const T0 = "2026-10-09T09:12:04.000Z";
const T1 = "2026-10-09T10:41:57.000Z";
const T2 = "2026-10-09T11:03:22.000Z";
const T3 = "2026-10-09T12:15:38.000Z";

const MODELS: ModelInfo[] = [
  {
    id: "qwen2.5:3b-instruct",
    label: "Qwen2.5 3B Instruct",
    provider: "ollama",
    remote: false,
    tier: "min",
    capabilities: ["plan", "chat"],
    available: true,
    size_hint: "1.9 GB",
    notes: "Q4_K_M · default reasoner on the 8 GB tier",
  },
  {
    id: "qwen2.5-coder:3b",
    label: "Qwen2.5 Coder 3B",
    provider: "ollama",
    remote: false,
    tier: "min",
    capabilities: ["code"],
    available: true,
    size_hint: "1.9 GB",
    notes: "Q4_K_M · selected for code and script tasks",
  },
  {
    id: "qwen2.5:1.5b-instruct",
    label: "Qwen2.5 1.5B Instruct",
    provider: "ollama",
    remote: false,
    tier: "min",
    capabilities: ["chat"],
    available: true,
    size_hint: "1.0 GB",
    notes: "Fast utility model for short answers",
  },
  {
    id: "moondream2",
    label: "Moondream2",
    provider: "ollama",
    remote: false,
    tier: "min",
    capabilities: ["vision"],
    available: false,
    size_hint: "1.8 GB",
    notes: "Not pulled yet — required for scanned drawings",
  },
  {
    id: "bge-small-en-v1.5",
    label: "BGE Small EN v1.5",
    provider: "sentence-transformers",
    remote: false,
    tier: "min",
    capabilities: ["embed"],
    available: true,
    size_hint: "130 MB",
    notes: "CPU embeddings for the local vector store",
  },
  {
    id: "gpt-4o-mini",
    label: "GPT-4o mini",
    provider: "openai",
    remote: true,
    tier: "remote",
    capabilities: ["chat", "vision"],
    available: false,
    size_hint: null,
    notes: "Disabled while AIRGAP=true",
  },
];

const DOCUMENTS: Document[] = [
  {
    id: "doc-ins-2024-07",
    filename: "INS-2024-07-Unit12-Inspection.pdf",
    content_type: "application/pdf",
    size_bytes: 4_382_208,
    chunk_count: 18,
    status: "indexed",
    created_at: T0,
  },
  {
    id: "doc-sop-tank-entry",
    filename: "MRPL-SOP-Tank-Entry-v4.md",
    content_type: "text/markdown",
    size_bytes: 128_410,
    chunk_count: 9,
    status: "indexed",
    created_at: T0,
  },
  {
    id: "doc-q3-financials",
    filename: "Q3-Financials-Units.xlsx",
    content_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    size_bytes: 1_146_880,
    chunk_count: 46,
    status: "indexed",
    created_at: T1,
  },
];

function citation(documentId: string, filename: string, page: number, span: string): Citation {
  return { document_id: documentId, filename, page, span, score: 0.82 };
}

const CHUNKS: Chunk[] = [
  {
    id: "chk-ins-001",
    text: "External visual inspection of Unit 12 (FCC) carried out on 07-Jul-2026. Two hairline cracks observed on the riser support bracket, neither through-thickness. UT thickness within design envelope.",
    citation: citation(
      "doc-ins-2024-07",
      "INS-2024-07-Unit12-Inspection.pdf",
      3,
      "Two hairline cracks observed on the riser support bracket, neither through-thickness.",
    ),
  },
  {
    id: "chk-ins-002",
    text: "Recommendation: weld-repair the riser bracket during the next turnaround window and re-inspect within 90 days. No immediate restriction on operation.",
    citation: citation(
      "doc-ins-2024-07",
      "INS-2024-07-Unit12-Inspection.pdf",
      4,
      "Recommendation: weld-repair the riser bracket during the next turnaround window.",
    ),
  },
  {
    id: "chk-ins-003",
    text: "Corrosion under insulation (CUI) survey on the corresponding piping spool found surface pitting up to 1.4 mm; remaining wall 6.8 mm against a 4.5 mm minimum.",
    citation: citation(
      "doc-ins-2024-07",
      "INS-2024-07-Unit12-Inspection.pdf",
      6,
      "surface pitting up to 1.4 mm; remaining wall 6.8 mm",
    ),
  },
  {
    id: "chk-sop-001",
    text: "Tank entry requires a signed permit, gas test within 30 minutes of entry, and a two-person rescue team stationed at the hatch.",
    citation: citation(
      "doc-sop-tank-entry",
      "MRPL-SOP-Tank-Entry-v4.md",
      2,
      "requires a signed permit, gas test within 30 minutes of entry",
    ),
  },
  {
    id: "chk-sop-002",
    text: "Isolation must be double-blocked and bleed-verified; single isolation is permitted only with written approval from the duty manager.",
    citation: citation(
      "doc-sop-tank-entry",
      "MRPL-SOP-Tank-Entry-v4.md",
      5,
      "Isolation must be double-blocked and bleed-verified",
    ),
  },
  {
    id: "chk-q3-001",
    text: "Unit 12 utilisation for Q3: 91.4% against a plan of 88.0%. Unplanned downtime of 41 hours attributed to the exchanger leak in week 32.",
    citation: citation(
      "doc-q3-financials",
      "Q3-Financials-Units.xlsx",
      1,
      "Unit 12 utilisation for Q3: 91.4% against a plan of 88.0%",
    ),
  },
  {
    id: "chk-q3-002",
    text: "Energy cost per tonne improved 6.2% quarter on quarter after the waste-heat recovery commissioning.",
    citation: citation(
      "doc-q3-financials",
      "Q3-Financials-Units.xlsx",
      2,
      "Energy cost per tonne improved 6.2% quarter on quarter",
    ),
  },
];

const APPROVAL_NOTE_CODE = `"""Approval note drafter for scanned inspection findings."""

from __future__ import annotations

from docx import Document
from docx.shared import Pt

FINDING = "riser bracket hairline cracking (Unit 12)"


def build_note(finding: str, recommendation: str) -> Document:
    doc = Document()
    doc.add_heading("Approval Note", level=0)
    doc.add_heading(finding, level=1)
    for line in recommendation.split(". "):
        if line.strip():
            doc.add_paragraph(line.strip(), style="List Bullet")
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    return doc


if __name__ == "__main__":
    note = build_note(
        FINDING,
        "Approve weld repair of the riser bracket in the next turnaround. "
        "Re-inspect within 90 days. No restriction on current operation.",
    )
    note.save("Approval-Note-Unit12.docx")
    print("wrote Approval-Note-Unit12.docx")
`;

const TASK_STEPS_DONE: TaskStep[] = [
  {
    index: 1,
    kind: "tool_call",
    title: "Retrieve cited excerpts from the knowledge base",
    detail: "3 excerpts returned with page-level citations",
    tool: "doc_search",
    args: { query: "Unit 12 inspection findings riser bracket", top_k: 3 },
    result: { count: 3 },
    ok: true,
    started_at: T1,
    ended_at: T1,
  },
  {
    index: 2,
    kind: "tool_call",
    title: "Draft the approval note deliverable",
    detail: "wrote Approval-Note-Unit12.docx (48.2 KB)",
    tool: "docx_writer",
    args: { filename: "Approval-Note-Unit12.docx", sections: 3 },
    result: { bytes: 49_360 },
    ok: true,
    started_at: T1,
    ended_at: T1,
  },
  {
    index: 3,
    kind: "step_start",
    title: "Writing the answer",
    detail: null,
    tool: null,
    args: null,
    result: null,
    ok: null,
    started_at: T1,
    ended_at: T1,
  },
];

const TASK_STEPS_CODE: TaskStep[] = [
  {
    index: 1,
    kind: "tool_call",
    title: "Read the Q3 utilisation sheet",
    detail: "read 46 rows, 6 columns",
    tool: "spreadsheet",
    args: { filename: "Q3-Financials-Units.xlsx", sheet: "Utilisation" },
    result: { rows: 46 },
    ok: true,
    started_at: T2,
    ended_at: T2,
  },
  {
    index: 2,
    kind: "tool_call",
    title: "Write and execute the analysis script",
    detail: "exit 0 · stdout: reconciled 46 rows",
    tool: "code_exec",
    args: { language: "python", filename: "analyze_units.py" },
    result: { exit_code: 0 },
    ok: true,
    started_at: T2,
    ended_at: T2,
  },
  {
    index: 3,
    kind: "step_start",
    title: "Writing the answer",
    detail: null,
    tool: null,
    args: null,
    result: null,
    ok: null,
    started_at: T2,
    ended_at: T2,
  },
];

const ARTIFACTS: Artifact[] = [
  {
    id: "art-approval-note",
    task_id: "task-a17f9c2e",
    filename: "Approval-Note-Unit12.docx",
    kind: "docx",
    size_bytes: 49_360,
    created_at: T1,
  },
  {
    id: "art-analyze-units",
    task_id: "task-b42d1e08",
    filename: "analyze_units.py",
    kind: "code",
    size_bytes: 3_184,
    created_at: T2,
  },
  {
    id: "art-tank-briefing",
    task_id: "task-a17f9c2e",
    filename: "Tank-Entry-Briefing.pptx",
    kind: "pptx",
    size_bytes: 214_016,
    created_at: T1,
  },
];

const TASKS: Task[] = [
  {
    id: "task-a17f9c2e",
    prompt:
      "Read the scanned Unit-12 inspection report and draft an approval note as a Word file",
    status: "done",
    model_id: "qwen2.5:3b-instruct",
    created_at: T1,
    updated_at: T1,
    steps: TASK_STEPS_DONE,
    artifacts: ARTIFACTS.filter((a) => a.task_id === "task-a17f9c2e"),
    error: null,
  },
  {
    id: "task-b42d1e08",
    prompt: "Write a python script that reconciles Q3 pump utilisation against plan",
    status: "done",
    model_id: "qwen2.5-coder:3b",
    created_at: T2,
    updated_at: T2,
    steps: TASK_STEPS_CODE,
    artifacts: ARTIFACTS.filter((a) => a.task_id === "task-b42d1e08"),
    error: null,
  },
  {
    id: "task-c90a4f51",
    prompt: "Summarise the board correspondence with the remote GPT model",
    status: "error",
    model_id: "gpt-4o-mini",
    created_at: T3,
    updated_at: T3,
    steps: [],
    artifacts: [],
    error: "AIRGAP blocks remote providers; pick a local model and retry",
  },
];

const AUDIT: AuditEvent[] = [
  {
    id: "aud-0006",
    type: "egress.block",
    actor: "EgressGuard",
    detail: "blocked https://api.openai.com/v1/chat/completions",
    data: { host: "api.openai.com", airgap: true },
    created_at: T3,
  },
  {
    id: "aud-0005",
    type: "model.select",
    actor: "router",
    detail: "routed capability=code → qwen2.5-coder:3b (tier=min, local)",
    data: { capability: "code", model_id: "qwen2.5-coder:3b" },
    created_at: T2,
  },
  {
    id: "aud-0004",
    type: "artifact.write",
    actor: "docx_writer",
    detail: "wrote Approval-Note-Unit12.docx (48.2 KB)",
    data: { artifact_id: "art-approval-note" },
    created_at: T1,
  },
  {
    id: "aud-0003",
    type: "task.create",
    actor: "operator",
    detail: "task-a17f9c2e queued with 1 attachment",
    data: { task_id: "task-a17f9c2e" },
    created_at: T1,
  },
  {
    id: "aud-0002",
    type: "document.upload",
    actor: "operator",
    detail: "indexed INS-2024-07-Unit12-Inspection.pdf → 18 chunks",
    data: { document_id: "doc-ins-2024-07", chunks: 18 },
    created_at: T0,
  },
  {
    id: "aud-0001",
    type: "system.start",
    actor: "system",
    detail: "air-gap mode enabled · no external transport permitted",
    data: { airgap: true },
    created_at: T0,
  },
];

export function createSeed(): SeedData {
  return {
    health: {
      status: "ok",
      version: "0.1.0",
      airgap: true,
      hardware_tier: "min (8 GB / i3 / 2 GB GPU)",
      models: MODELS.filter((model) => model.available).length,
      models_ready: true,
    },
    egress: {
      airgap: true,
      blocked: 7,
      allowed_local: 4,
      external_allowed: 0,
      local_endpoints: [
        "127.0.0.1:8000 (backend)",
        "127.0.0.1:11434 (ollama)",
        "localhost:5173 (vite)",
        "127.0.0.1:6379 (vector store)",
      ],
    },
    models: MODELS,
    documents: DOCUMENTS,
    chunks: CHUNKS,
    tasks: TASKS,
    artifacts: ARTIFACTS,
    artifactText: {
      "art-analyze-units": APPROVAL_NOTE_CODE,
      "art-approval-note":
        "Approval Note\n\nUnit 12 (FCC) — riser bracket hairline cracking\n\n" +
        "Approve weld repair of the riser bracket in the next turnaround window. " +
        "Re-inspect within 90 days. No restriction on current operation.\n\n" +
        "Evidence: INS-2024-07-Unit12-Inspection.pdf p.3, p.4",
      "art-tank-briefing": "Tank Entry Briefing — 14 slides (preview unavailable, download to view)",
    },
    audit: AUDIT,
  };
}
