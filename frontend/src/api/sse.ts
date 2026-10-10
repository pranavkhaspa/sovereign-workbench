import { ApiError } from "./client";
import type { AgentEvent, AgentEventType, TaskCreate } from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

function isAgentEventType(value: unknown): value is AgentEventType {
  return (
    value === "task_created" ||
    value === "plan" ||
    value === "step_start" ||
    value === "tool_call" ||
    value === "tool_result" ||
    value === "token" ||
    value === "artifact" ||
    value === "done" ||
    value === "error"
  );
}

function parseEvent(data: string, eventName: string | undefined): AgentEvent | null {
  try {
    const parsed: unknown = JSON.parse(data);
    if (typeof parsed !== "object" || parsed === null) return null;
    const record = parsed as Record<string, unknown>;
    const type = record.type ?? eventName;
    const nestedData = record.data;
    const nestedRecord =
      typeof nestedData === "object" && nestedData !== null
        ? (nestedData as Record<string, unknown>)
        : null;
    const taskId = record.task_id ?? nestedRecord?.task_id;
    if (!isAgentEventType(type) || typeof taskId !== "string") {
      return null;
    }
    const eventData = record.data;
    return {
      type,
      task_id: taskId,
      at: typeof record.at === "string" ? record.at : new Date().toISOString(),
      data:
        typeof eventData === "object" && eventData !== null
          ? (eventData as Record<string, unknown>)
          : record,
    };
  } catch {
    return null;
  }
}

function parseFrame(frame: string): AgentEvent | null {
  const data = frame
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim())
    .join("\n");
  if (!data || data === "[DONE]") return null;
  const eventName = frame
    .split(/\r?\n/)
    .find((line) => line.startsWith("event:"))
    ?.slice(6)
    .trim();
  return parseEvent(data, eventName);
}

export async function streamTask(
  payload: TaskCreate,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(apiUrl("/api/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (error) {
    if (signal?.aborted) throw new DOMException("Stream stopped", "AbortError");
    const message = error instanceof Error ? error.message : "network request failed";
    throw new ApiError(`Stream unavailable: ${message}`, 0);
  }
  if (!response.ok || !response.body) {
    const message = response.ok
      ? "The backend returned an empty stream"
      : `${response.status} ${response.statusText}`;
    throw new ApiError(message, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const event = parseFrame(frame);
        if (event) onEvent(event);
      }
    }
    buffer += decoder.decode();
    const finalEvent = parseFrame(buffer);
    if (finalEvent) onEvent(finalEvent);
  } finally {
    reader.releaseLock();
  }
}
