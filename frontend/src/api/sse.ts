import type { AgentEvent, AgentEventType } from "./types";

export function isAgentEventType(value: unknown): value is AgentEventType {
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

function envelopeId(record: Record<string, unknown>): number | undefined {
  return typeof record.id === "number" && Number.isFinite(record.id) ? record.id : undefined;
}

export function parseEvent(
  data: string,
  eventName: string | undefined,
  idLine?: number,
): AgentEvent | null {
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
    const id = envelopeId(record) ?? idLine;
    return {
      ...(id === undefined ? {} : { id }),
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

function frameId(frame: string): number | undefined {
  const line = frame
    .split(/\r?\n/)
    .find((candidate) => candidate.startsWith("id:"));
  if (!line) return undefined;
  const value = Number(line.slice(3).trim());
  return Number.isFinite(value) ? value : undefined;
}

export function parseFrame(frame: string): AgentEvent | null {
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
  return parseEvent(data, eventName, frameId(frame));
}

export async function readSseStream(
  response: Response,
  onEvent: (event: AgentEvent) => void,
): Promise<void> {
  if (!response.body) return;
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
