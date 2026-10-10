// In-browser mock transport. Selected by VITE_USE_MOCK=true in transport.ts.
// It answers every §4 route from a seeded in-memory store and plays a scripted
// §3 agent stream on a timer, so the UI can be demoed without a backend.

import { createSeed } from "../../scripts/seed";
import { ApiError } from "./errors";
import type { Transport, UploadResult } from "./transport";
import type {
  AgentEvent,
  AgentEventType,
  Artifact,
  Chunk,
  Document,
  Task,
  TaskCreate,
  TaskStep,
} from "./types";

interface MockState {
  health: ReturnType<typeof createSeed>["health"];
  egress: ReturnType<typeof createSeed>["egress"];
  models: ReturnType<typeof createSeed>["models"];
  documents: Document[];
  chunks: Chunk[];
  tasks: Task[];
  artifacts: Artifact[];
  artifactText: Record<string, string>;
  audit: ReturnType<typeof createSeed>["audit"];
}

const REQUEST_DELAY_MS = 60;
const TOKEN_DELAY_MS = 18;

let state: MockState = createSeed();
let counter = 0;
const eventLog: Record<string, AgentEvent[]> = {};
const eventSeq: Record<string, number> = {};
const blobUrls = new Map<string, string>();

export function resetMock(): void {
  state = createSeed();
  for (const key of Object.keys(eventLog)) delete eventLog[key];
  for (const key of Object.keys(eventSeq)) delete eventSeq[key];
  for (const url of blobUrls.values()) {
    if (typeof URL.revokeObjectURL === "function") URL.revokeObjectURL(url);
  }
  blobUrls.clear();
  counter = 0;
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const onAbort = (): void => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

function newId(prefix: string): string {
  counter += 1;
  return `${prefix}-${Date.now().toString(36)}-${counter.toString(36)}`;
}

function now(): string {
  return new Date().toISOString();
}

function parseBody(body: RequestInit["body"]): unknown {
  if (typeof body !== "string") return body;
  try {
    return JSON.parse(body);
  } catch {
    return body;
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : {};
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNumber(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function health(): Record<string, unknown> {
  return {
    ...state.health,
    models: state.models.length,
    models_ready: state.models.some((model) => model.available),
  };
}

function listTasks(query: URLSearchParams): Task[] {
  const limit = asNumber(Number(query.get("limit")), 50);
  return [...state.tasks]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, Number.isFinite(limit) && limit > 0 ? limit : 50);
}

function findTask(id: string): Task {
  const task = state.tasks.find((item) => item.id === id);
  if (!task) throw new ApiError(`Task ${id} not found`, 404);
  return task;
}

function createTask(body: unknown): Task {
  const payload = asRecord(body);
  const task: Task = {
    id: newId("task"),
    prompt: asString(payload.prompt, "Untitled task"),
    status: "queued",
    model_id: typeof payload.model_id === "string" ? payload.model_id : null,
    created_at: now(),
    updated_at: now(),
    steps: [],
    artifacts: [],
    error: null,
  };
  state.tasks.unshift(task);
  eventLog[task.id] = [];
  eventSeq[task.id] = 0;
  return task;
}

function searchChunks(query: string, topK: number): Chunk[] {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return state.chunks.slice(0, topK);
  return state.chunks
    .map((chunk) => {
      const haystack = `${chunk.text} ${chunk.citation.filename}`.toLowerCase();
      const score = terms.reduce((total, term) => total + (haystack.includes(term) ? 1 : 0), 0);
      return { chunk, score };
    })
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, topK)
    .map((entry) => ({
      ...entry.chunk,
      citation: { ...entry.chunk.citation, score: Number((0.55 + entry.score * 0.11).toFixed(2)) },
    }));
}

function mimeFor(filename: string): string {
  if (filename.endsWith(".docx"))
    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  if (filename.endsWith(".pptx"))
    return "application/vnd.openxmlformats-officedocument.presentationml.presentation";
  if (filename.endsWith(".xlsx"))
    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  if (filename.endsWith(".pdf")) return "application/pdf";
  if (filename.endsWith(".md")) return "text/markdown";
  return "text/plain";
}

function route(
  method: string,
  path: string,
  query: URLSearchParams,
  body: unknown,
  init?: RequestInit,
): unknown {
  const segments = path.split("/").filter(Boolean);
  if (segments[0] !== "api") throw new ApiError(`Not found: ${path}`, 404);
  const resource = segments[1];
  const id = segments[2];
  const tail = segments[3];

  if (resource === "health" && id === "egress") return { ...state.egress };
  if (resource === "health") return health();
  if (resource === "audit" && id === "egress") return { ...state.egress };
  if (resource === "audit") {
    const typeFilter = query.get("type");
    const limit = asNumber(Number(query.get("limit")), 200);
    return state.audit
      .filter((event) => !typeFilter || event.type === typeFilter)
      .slice(0, limit > 0 ? limit : 200);
  }

  if (resource === "models") {
    if (id && method === "GET") {
      const model = state.models.find((item) => item.id === id);
      if (!model) throw new ApiError(`Model ${id} not found`, 404);
      return model;
    }
    return { models: state.models };
  }

  if (resource === "tasks") {
    if (!id) {
      if (method === "GET") return listTasks(query);
      if (method === "POST") return createTask(body);
    }
    if (id && !tail && method === "GET") return findTask(id);
    if (id && tail === "cancel" && method === "POST") {
      const task = findTask(id);
      task.status = "cancelled";
      task.updated_at = now();
      return { ok: true };
    }
  }

  if (resource === "documents") {
    if (!id && method === "GET") return state.documents;
    if (!id && method === "POST") {
      const file = init?.body instanceof FormData ? init.body.get("file") : null;
      const upload = file instanceof File ? file : null;
      const document: Document = {
        id: newId("doc"),
        filename: upload?.name ?? "upload.bin",
        content_type: upload?.type || "application/octet-stream",
        size_bytes: upload?.size ?? 0,
        chunk_count: Math.max(1, Math.round((upload?.size ?? 1024) / 1200)),
        status: "indexed",
        created_at: now(),
      };
      state.documents.unshift(document);
      const result: UploadResult = {
        document_id: document.id,
        chunks: document.chunk_count,
        status: document.status,
      };
      return result;
    }
    if (id === "search") {
      if (method === "POST") {
        const payload = asRecord(body);
        return searchChunks(asString(payload.query), asNumber(payload.top_k, 5));
      }
      return searchChunks(asString(query.get("q")), asNumber(Number(query.get("top_k")), 5));
    }
    if (id && method === "GET") {
      const document = state.documents.find((item) => item.id === id);
      if (!document) throw new ApiError(`Document ${id} not found`, 404);
      return document;
    }
    if (id && method === "DELETE") {
      state.documents = state.documents.filter((item) => item.id !== id);
      return { ok: true };
    }
  }

  if (resource === "artifacts") {
    if (!id) {
      const taskId = query.get("task_id");
      return state.artifacts.filter((artifact) => !taskId || artifact.task_id === taskId);
    }
    const artifact = state.artifacts.find((item) => item.id === id);
    if (!artifact) throw new ApiError(`Artifact ${id} not found`, 404);
    if (tail === "download") return artifact;
    return artifact;
  }

  throw new ApiError(`Not found: ${method} ${path}`, 404);
}

const ANSWER_APPROVAL = [
  "## Approval note ready",
  "",
  "The scanned **Unit 12** inspection report was read locally — no file left the workspace.",
  "",
  "- **Riser bracket** — two hairline cracks, neither through-thickness (p.3).",
  "- **CUI survey** — 1.4 mm pitting, 6.8 mm remaining wall against a 4.5 mm minimum (p.6).",
  "- **Utilisation** — 91.4% against a plan of 88.0% for Q3.",
  "",
  "### Recommendation",
  "",
  "Approve the weld repair in the next turnaround window and re-inspect within 90 days.",
  "There is no restriction on current operation.",
  "",
  "The deliverable `Approval-Note-Unit12.docx` is available under **Artifacts**.",
].join("\n");

const ANSWER_CODE = [
  "## Script verified in the sandbox",
  "",
  "`analyze_units.py` ran with **exit 0** and reconciled 46 rows against plan.",
  "",
  "| unit | plan | actual | delta |",
  "| --- | --- | --- | --- |",
  "| U-101 | 88.0% | 91.4% | +3.4 |",
  "| U-102 | 86.5% | 84.9% | −1.6 |",
  "",
  "The script is attached under **Artifacts** and can be copied or downloaded.",
].join("\n");

async function chatStream(
  payload: TaskCreate,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const isCode = /code|python|script|csv|reconcil|automat|spreadsheet/i.test(payload.prompt);
  const requested = payload.model_id?.trim();
  const modelId =
    requested && requested !== "auto"
      ? requested
      : isCode
        ? "qwen2.5-coder:3b"
        : "qwen2.5:3b-instruct";
  const taskId = newId("task");
  const task: Task = {
    id: taskId,
    prompt: payload.prompt,
    status: "running",
    model_id: modelId,
    created_at: now(),
    updated_at: now(),
    steps: [],
    artifacts: [],
    error: null,
  };
  state.tasks.unshift(task);
  eventLog[taskId] = [];
  eventSeq[taskId] = 0;

  const emit = (type: AgentEventType, data: Record<string, unknown>): void => {
    eventSeq[taskId] = (eventSeq[taskId] ?? 0) + 1;
    const event: AgentEvent = { id: eventSeq[taskId], type, task_id: taskId, at: now(), data };
    eventLog[taskId]?.push(event);
    onEvent(event);
  };

  const steps: TaskStep[] = [];
  task.steps = steps;
  let current: TaskStep | null = null;

  const startStep = (index: number, title: string): void => {
    current = {
      index,
      kind: "step_start",
      title,
      detail: null,
      tool: null,
      args: null,
      result: null,
      ok: null,
      started_at: now(),
      ended_at: null,
    };
    steps.push(current);
    emit("step_start", { index, title });
  };

  const callTool = (tool: string, args: Record<string, unknown>): void => {
    if (current) {
      current.kind = "tool_call";
      current.tool = tool;
      current.args = args;
    }
    emit("tool_call", { tool, args });
  };

  const toolResult = (
    tool: string,
    output: string,
    extra: Record<string, unknown> = {},
  ): void => {
    if (current) {
      current.ok = true;
      current.detail = output.slice(0, 160);
      current.result = extra;
      current.ended_at = now();
    }
    emit("tool_result", { tool, ok: true, output, error: null, ...extra });
  };

  const emitTokens = async (text: string): Promise<void> => {
    const tokens = text.match(/\s*\S+/g) ?? [];
    for (let index = 0; index < tokens.length; index += 5) {
      await sleep(TOKEN_DELAY_MS, signal);
      emit("token", { text: tokens.slice(index, index + 5).join("") });
    }
  };

  try {
    emit("task_created", { task_id: taskId, status: "running" });
    await sleep(220, signal);
    emit("plan", {
      model_id: modelId,
      capability: isCode ? "code" : "chat",
      steps: isCode
        ? [
            { title: "Read the Q3 utilisation sheet", tool: "spreadsheet", kind: "tool_call" },
            { title: "Write and execute the analysis script", tool: "code_exec", kind: "tool_call" },
            { title: "Writing the answer", tool: null, kind: "step_start" },
          ]
        : [
            {
              title: "Retrieve cited excerpts from the knowledge base",
              tool: "doc_search",
              kind: "tool_call",
            },
            { title: "Draft the approval note deliverable", tool: "docx_writer", kind: "tool_call" },
            { title: "Writing the answer", tool: null, kind: "step_start" },
          ],
    });

    if (isCode) {
      startStep(1, "Read the Q3 utilisation sheet");
      callTool("spreadsheet", { filename: "Q3-Financials-Units.xlsx", sheet: "Utilisation" });
      await sleep(520, signal);
      toolResult("spreadsheet", "read 46 rows × 6 columns", { rows: 46 });

      startStep(2, "Write and execute the analysis script");
      callTool("code_exec", { language: "python", filename: "analyze_units.py" });
      await sleep(680, signal);
      const artifact = registerArtifact(task, "analyze_units.py", "code", 3_184);
      toolResult("code_exec", "exit 0 · reconciled 46 rows against plan", { exit_code: 0 });
      emit("artifact", { ...artifact });

      startStep(3, "Writing the answer");
      await sleep(280, signal);
      await emitTokens(ANSWER_CODE);
    } else {
      startStep(1, "Retrieve cited excerpts from the knowledge base");
      callTool("doc_search", { query: "Unit 12 inspection findings riser bracket", top_k: 3 });
      await sleep(520, signal);
      const citations = state.chunks
        .filter((chunk) => chunk.citation.filename.includes("INS-2024-07"))
        .slice(0, 3)
        .map((chunk) => chunk.citation);
      toolResult("doc_search", "3 excerpts returned with page-level citations", {
        count: 3,
        citations,
      });

      startStep(2, "Draft the approval note deliverable");
      callTool("docx_writer", { filename: "Approval-Note-Unit12.docx", sections: 3 });
      await sleep(640, signal);
      const artifact = registerArtifact(task, "Approval-Note-Unit12.docx", "docx", 49_360);
      toolResult("docx_writer", "wrote Approval-Note-Unit12.docx (48.2 KB)", { bytes: 49_360 });
      emit("artifact", { ...artifact });

      startStep(3, "Writing the answer");
      await sleep(280, signal);
      await emitTokens(ANSWER_APPROVAL);
    }

    await sleep(220, signal);
    task.status = "done";
    task.updated_at = now();
    emit("done", {
      artifacts: state.artifacts
        .filter((artifact) => artifact.task_id === taskId)
        .map((artifact) => artifact.filename),
    });
  } catch (error) {
    task.status = error instanceof DOMException && error.name === "AbortError" ? "cancelled" : "error";
    task.updated_at = now();
    if (!(error instanceof DOMException && error.name === "AbortError")) {
      task.error = error instanceof Error ? error.message : "mock stream failed";
    }
    throw error;
  }
}

function registerArtifact(task: Task, filename: string, kind: string, size: number): Artifact {
  const artifact: Artifact = {
    id: newId("art"),
    task_id: task.id,
    filename,
    kind,
    size_bytes: size,
    created_at: now(),
  };
  state.artifacts.unshift(artifact);
  task.artifacts.push(artifact);
  return artifact;
}

async function taskEventsStream(
  taskId: string,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
  after?: number,
): Promise<void> {
  const log = eventLog[taskId];
  if (!log) throw new ApiError(`Task ${taskId} not found`, 404);
  const cursor = after !== undefined && after > 0 ? after : 0;
  for (const event of log) {
    if (cursor > 0 && (event.id ?? 0) <= cursor) continue;
    await sleep(15, signal);
    onEvent(event);
  }
}

function downloadUrl(id: string): string {
  const artifact = state.artifacts.find((item) => item.id === id);
  if (!artifact) return "";
  const cached = blobUrls.get(id);
  if (cached) return cached;
  if (typeof URL === "undefined" || typeof URL.createObjectURL !== "function") return "";
  const text = state.artifactText[id] ?? `mock artifact: ${artifact.filename}\n`;
  const url = URL.createObjectURL(new Blob([text], { type: mimeFor(artifact.filename) }));
  blobUrls.set(id, url);
  return url;
}

export const mockTransport: Transport = {
  async request<T>(path: string, init?: RequestInit): Promise<T> {
    const [pathname, search] = path.split("?");
    const method = (init?.method ?? "GET").toUpperCase();
    await sleep(REQUEST_DELAY_MS);
    return route(method, pathname ?? path, new URLSearchParams(search ?? ""), parseBody(init?.body), init) as T;
  },
  chatStream,
  taskEventsStream,
  async upload(file: File): Promise<UploadResult> {
    const form = new FormData();
    form.append("file", file);
    return mockTransport.request<UploadResult>("/api/documents", {
      method: "POST",
      body: form,
    });
  },
  downloadUrl,
  async readArtifact(id: string): Promise<string> {
    const text = state.artifactText[id];
    if (text === undefined) throw new ApiError(`Artifact ${id} not found`, 404);
    await sleep(REQUEST_DELAY_MS);
    return text;
  },
};
