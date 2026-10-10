import { describe, expect, it } from "vitest";

import { isAgentEventType, parseEvent, parseFrame } from "./sse";

const TASK_ID = "task-abc";

function frame(payload: Record<string, unknown>, eventName?: string): string {
  const lines: string[] = [];
  if (eventName) lines.push(`event: ${eventName}`);
  lines.push(`data: ${JSON.stringify(payload)}`);
  return lines.join("\n");
}

describe("isAgentEventType", () => {
  it("accepts every documented event type", () => {
    for (const type of ["task_created", "plan", "tool_call", "token", "error"]) {
      expect(isAgentEventType(type)).toBe(true);
    }
    expect(isAgentEventType("nonsense")).toBe(false);
    expect(isAgentEventType(7)).toBe(false);
  });
});

describe("parseFrame", () => {
  it("parses a typed frame with nested data", () => {
    const event = parseFrame(
      frame({
        type: "tool_call",
        task_id: TASK_ID,
        at: "2026-10-09T10:00:00.000Z",
        data: { tool: "doc_search", args: { top_k: 3 } },
      }),
    );
    expect(event).toMatchObject({
      type: "tool_call",
      task_id: TASK_ID,
      at: "2026-10-09T10:00:00.000Z",
      data: { tool: "doc_search", args: { top_k: 3 } },
    });
  });

  it("falls back to the SSE event name when the payload carries no type", () => {
    const event = parseFrame(
      frame({ task_id: TASK_ID, at: "2026-10-09T10:00:00.000Z", data: { text: "Unit 12" } }, "token"),
    );
    expect(event?.type).toBe("token");
    expect(event?.data).toEqual({ text: "Unit 12" });
  });

  it("keeps the whole record as data when data is not an object", () => {
    const event = parseFrame(frame({ type: "done", task_id: TASK_ID, artifacts: ["note.docx"] }));
    expect(event?.data).toMatchObject({ artifacts: ["note.docx"] });
  });

  it("reads a task id from nested data", () => {
    const event = parseFrame(
      frame({ type: "plan", data: { task_id: TASK_ID, capability: "chat" } }, "plan"),
    );
    expect(event?.task_id).toBe(TASK_ID);
    expect(event?.data).toEqual({ task_id: TASK_ID, capability: "chat" });
  });

  it("ignores the [DONE] sentinel", () => {
    expect(parseFrame("data: [DONE]")).toBeNull();
  });

  it("ignores unknown types, missing task ids and malformed JSON", () => {
    expect(parseFrame(frame({ type: "mystery", task_id: TASK_ID }))).toBeNull();
    expect(parseFrame(frame({ type: "done" }))).toBeNull();
    expect(parseFrame("data: {not-json}")).toBeNull();
    expect(parseFrame("")).toBeNull();
  });

  it("stamps a timestamp when the payload omits one", () => {
    const event = parseFrame(frame({ type: "step_start", task_id: TASK_ID, data: { index: 1 } }));
    expect(typeof event?.at).toBe("string");
    expect(Number.isNaN(new Date(event?.at ?? "").getTime())).toBe(false);
  });
});

describe("parseEvent", () => {
  it("returns null for non-object payloads", () => {
    expect(parseEvent('"just a string"', undefined)).toBeNull();
    expect(parseEvent("null", "token")).toBeNull();
  });
});
