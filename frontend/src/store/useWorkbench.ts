import { create } from "zustand";

import { api, streamTask, streamTaskEvents } from "../api/client";
import type {
  AgentEvent,
  AgentEventType,
  Citation,
  Task,
  TaskCreate,
  TaskStep,
} from "../api/types";

export type StreamState =
  "idle" | "connecting" | "streaming" | "complete" | "stopped" | "error" | "disconnected";

export interface TimelineEntry {
  id: string;
  type: AgentEventType;
  label: string;
  detail?: string;
  data: Record<string, unknown>;
  at: string;
  ok?: boolean | null;
}

interface WorkbenchState {
  running: boolean;
  streamState: StreamState;
  taskId: string | null;
  answer: string;
  timeline: TimelineEntry[];
  citations: Citation[];
  error: string | null;
  run: (payload: TaskCreate) => Promise<void>;
  reconnect: () => Promise<void>;
  stop: () => void;
  reset: () => void;
}

let counter = 0;
let activeController: AbortController | null = null;
let lastEventId = 0;

const nextId = () => `entry-${Date.now()}-${counter++}`;

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function describe(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === undefined || value === null) return "";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function taskStepEvent(taskId: string, step: TaskStep): AgentEvent {
  const knownTypes: AgentEventType[] = [
    "plan",
    "step_start",
    "tool_call",
    "tool_result",
    "artifact",
    "done",
    "error",
  ];
  const type = knownTypes.includes(step.kind as AgentEventType)
    ? (step.kind as AgentEventType)
    : "step_start";
  return {
    type,
    task_id: taskId,
    at: step.started_at ?? new Date().toISOString(),
    data: {
      index: step.index,
      title: step.title,
      detail: step.detail,
      tool: step.tool,
      args: step.args,
      result: step.result,
      ok: step.ok,
      output: step.detail,
    },
  };
}

function mergeRecoveredSteps(current: TimelineEntry[], task: Task): TimelineEntry[] {
  const existing = new Set(
    current.map(
      (entry) =>
        `${entry.type}:${typeof entry.data.index === "number" ? entry.data.index : entry.at}`,
    ),
  );
  const recovered = task.steps
    .filter((step) => !existing.has(`${step.kind}:${step.index}`))
    .map((step) => addEntry(taskStepEvent(task.id, step)));
  const merged = [...current, ...recovered];
  if (task.status === "done" && !merged.some((entry) => entry.type === "done")) {
    merged.push(
      addEntry({
        type: "done",
        task_id: task.id,
        at: task.updated_at,
        data: { recovered: true },
      }),
    );
  }
  return merged;
}

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(resolve, ms);
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timer);
        reject(new DOMException("Reconnect stopped", "AbortError"));
      },
      { once: true },
    );
  });
}

function addEntry(event: AgentEvent): TimelineEntry {
  const data = event.data;
  switch (event.type) {
    case "task_created":
      return {
        id: nextId(),
        type: event.type,
        label: "Task accepted",
        detail: "Stream opened",
        data,
        at: event.at,
      };
    case "plan": {
      const steps = Array.isArray(data.steps) ? data.steps : [];
      const titles = steps.map((step) => {
        if (typeof step === "object" && step !== null && "title" in step) {
          return asString(step.title, "Untitled step");
        }
        return "Untitled step";
      });
      const revised = data.replanned === true;
      return {
        id: nextId(),
        type: event.type,
        label: `${revised ? "Plan revised" : "Plan ready"} · ${steps.length} ${steps.length === 1 ? "step" : "steps"}`,
        detail: titles.join("  →  "),
        data,
        at: event.at,
      };
    }
    case "step_start":
      return {
        id: nextId(),
        type: event.type,
        label: asString(data.title, "Agent step started"),
        detail: data.index === undefined ? undefined : `Step ${asString(data.index)}`,
        data,
        at: event.at,
      };
    case "tool_call":
      return {
        id: nextId(),
        type: event.type,
        label: `Calling ${asString(data.tool, "local tool")}`,
        detail: describe(data.args ?? {}),
        data,
        at: event.at,
      };
    case "tool_result":
      return {
        id: nextId(),
        type: event.type,
        label: `${data.ok === false ? "Tool failed" : "Tool returned"} · ${asString(data.tool, "local tool")}`,
        detail: asString(data.output, asString(data.error)),
        data,
        at: event.at,
        ok: typeof data.ok === "boolean" ? data.ok : null,
      };
    case "artifact":
      return {
        id: nextId(),
        type: event.type,
        label: `Artifact ready · ${asString(data.filename, "download")}`,
        detail: typeof data.kind === "string" ? data.kind.toUpperCase() : undefined,
        data,
        at: event.at,
      };
    case "done":
      return {
        id: nextId(),
        type: event.type,
        label: "Run complete",
        detail: "The local agent finished this task.",
        data,
        at: event.at,
      };
    case "error":
      return {
        id: nextId(),
        type: event.type,
        label: "Agent error",
        detail: asString(data.message, "The agent reported an error."),
        data,
        at: event.at,
        ok: false,
      };
    case "token":
      return {
        id: nextId(),
        type: event.type,
        label: "Answer stream",
        data,
        at: event.at,
      };
  }
}

function citationKey(citation: Citation): string {
  return `${citation.document_id}:${citation.page ?? "-"}:${citation.span ?? "-"}`;
}

function mergeCitations(current: Citation[], data: Record<string, unknown>): Citation[] {
  const raw = data.citations;
  if (!Array.isArray(raw) || raw.length === 0) return current;
  const merged = [...current];
  const seen = new Set(merged.map(citationKey));
  for (const item of raw) {
    if (typeof item !== "object" || item === null) continue;
    const citation = item as Citation;
    if (typeof citation.document_id !== "string" || typeof citation.filename !== "string") continue;
    const key = citationKey(citation);
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(citation);
  }
  return merged;
}

export const useWorkbench = create<WorkbenchState>((set, get) => ({
  running: false,
  streamState: "idle",
  taskId: null,
  answer: "",
  timeline: [],
  citations: [],
  error: null,

  reset: () => {
    lastEventId = 0;
    set({
      running: false,
      streamState: "idle",
      taskId: null,
      answer: "",
      timeline: [],
      citations: [],
      error: null,
    });
  },

  stop: () => {
    const taskId = get().taskId;
    activeController?.abort();
    activeController = null;
    set({ running: false, streamState: "stopped", error: null });
    if (taskId) void api.cancelTask(taskId).catch(() => undefined);
  },

  reconnect: async () => {
    const taskId = get().taskId;
    if (!taskId) return;
    activeController?.abort();
    const controller = new AbortController();
    activeController = controller;
    set({ running: true, streamState: "connecting", error: null });

    // Resume the persisted event stream from the cursor so replayed token text
    // never duplicates what is already on screen. Without a cursor (fresh page)
    // the whole history is rebuilt from a full replay.
    const resume = lastEventId > 0;
    let terminal = false;
    let replayed = 0;
    let timeline: TimelineEntry[] = resume ? get().timeline : [];
    let answer = resume ? get().answer : "";
    if (!resume) set({ answer: "", timeline: [] });
    const handle = (event: AgentEvent): void => {
      if (activeController !== controller) return;
      replayed += 1;
      if (typeof event.id === "number" && event.id > lastEventId) {
        lastEventId = event.id;
      }
      if (event.type === "task_created") {
        set({ taskId: asString(event.data.task_id, event.task_id), streamState: "streaming" });
      }
      if (event.type === "token") {
        answer += asString(event.data.text);
        set({ answer });
        return;
      }
      timeline = [...timeline, addEntry(event)];
      set({ timeline, citations: mergeCitations(get().citations, event.data) });
      if (event.type === "done") {
        terminal = true;
        set({ running: false, streamState: "complete" });
      }
      if (event.type === "error") {
        terminal = true;
        set({
          running: false,
          streamState: "error",
          error: asString(event.data.message, "The agent reported an error."),
        });
      }
    };

    try {
      await streamTaskEvents(taskId, handle, controller.signal, resume ? lastEventId : undefined);
    } catch {
      // Fall through to the step-polling fallback below.
    }
    if (activeController !== controller) return;
    if (replayed > 0 && terminal) {
      activeController = null;
      return;
    }

    try {
      let task: Task | null = null;
      for (let attempt = 0; attempt < 12; attempt += 1) {
        task = await api.task(taskId, controller.signal);
        set((state) => ({ timeline: mergeRecoveredSteps(state.timeline, task as Task) }));
        if (task.status === "done" || task.status === "error" || task.status === "cancelled") break;
        await wait(1000, controller.signal);
      }
      if (!task) return;
      if (task.status === "done") {
        set({
          running: false,
          streamState: "complete",
          error: get().answer
            ? null
            : "Task completed while disconnected. Review the recovered trace and artifacts.",
        });
      } else if (task.status === "error") {
        set({
          running: false,
          streamState: "error",
          error: task.error ?? "The backend task failed.",
        });
      } else if (task.status === "cancelled") {
        set({ running: false, streamState: "stopped", error: null });
      } else {
        set({
          running: false,
          streamState: "disconnected",
          error: "The backend task is still active. Reconnect again to refresh its state.",
        });
      }
    } catch (error) {
      if (activeController !== controller) return;
      if (controller.signal.aborted) {
        set({ running: false, streamState: "stopped" });
      } else {
        set({
          running: false,
          streamState: "disconnected",
          error:
            error instanceof Error ? `Reconnect failed: ${error.message}` : "Reconnect failed.",
        });
      }
    } finally {
      if (activeController === controller) activeController = null;
    }
  },

  run: async (payload) => {
    activeController?.abort();
    const controller = new AbortController();
    activeController = controller;
    lastEventId = 0;
    set({
      running: true,
      streamState: "connecting",
      taskId: null,
      answer: "",
      timeline: [],
      citations: [],
      error: null,
    });

    let terminal = false;
    const handle = (event: AgentEvent) => {
      if (activeController !== controller) return;
      if (typeof event.id === "number" && event.id > lastEventId) {
        lastEventId = event.id;
      }
      if (event.type === "task_created") {
        set({ taskId: asString(event.data.task_id, event.task_id), streamState: "streaming" });
      }
      if (event.type !== "token") {
        set((state) => ({ timeline: [...state.timeline, addEntry(event)] }));
      }
      if (event.type === "tool_result" || event.type === "done") {
        set((state) => ({ citations: mergeCitations(state.citations, event.data) }));
      }
      if (event.type === "token") {
        set((state) => ({ answer: state.answer + asString(event.data.text) }));
      }
      if (event.type === "done") {
        terminal = true;
        set({ running: false, streamState: "complete" });
      }
      if (event.type === "error") {
        terminal = true;
        set({
          running: false,
          streamState: "error",
          error: asString(event.data.message, "The agent reported an error."),
        });
      }
    };

    try {
      await streamTask(payload, handle, controller.signal);
      if (activeController === controller && !terminal && get().running) {
        set({
          running: false,
          streamState: "disconnected",
          error: "The event stream ended before the task completed.",
        });
      }
    } catch (error) {
      if (activeController !== controller) return;
      if (controller.signal.aborted) {
        set({ running: false, streamState: "stopped" });
      } else if (get().taskId) {
        set({
          running: false,
          streamState: "disconnected",
          error:
            error instanceof Error
              ? `Live stream disconnected: ${error.message}`
              : "Live stream disconnected.",
        });
      } else {
        set({
          running: false,
          streamState: "error",
          error: error instanceof Error ? error.message : "The event stream failed.",
        });
      }
    } finally {
      if (activeController === controller) activeController = null;
    }
  },
}));
