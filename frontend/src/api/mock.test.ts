import { beforeEach, describe, expect, it } from "vitest";

import { mockTransport, resetMock } from "./mock";
import type { AgentEvent, Document, ModelList, TaskCreate, Task } from "./types";

function payload(prompt: string, modelId?: string): TaskCreate {
  return {
    prompt,
    model_id: modelId ?? null,
    options: { allow_network: false, write_files: true, run_code: false },
  };
}

function typesOf(events: AgentEvent[]): string[] {
  return events.map((event) => event.type);
}

beforeEach(() => {
  resetMock();
});

describe("mock request routes", () => {
  it("answers /api/models with the seeded registry", async () => {
    const list = await mockTransport.request<ModelList>("/api/models");
    expect(list.models.length).toBeGreaterThanOrEqual(5);
    expect(list.models.map((model) => model.id)).toContain("qwen2.5:3b-instruct");
    expect(list.models.some((model) => model.remote)).toBe(true);
  });

  it("deletes a document so it disappears from the index", async () => {
    const before = await mockTransport.request<Document[]>("/api/documents");
    const target = before[0];
    expect(target).toBeDefined();

    await mockTransport.request<{ ok: boolean }>(`/api/documents/${target?.id}`, {
      method: "DELETE",
    });

    const after = await mockTransport.request<Document[]>("/api/documents");
    expect(after).toHaveLength(before.length - 1);
    expect(after.find((doc) => doc.id === target?.id)).toBeUndefined();

    await expect(
      mockTransport.request(`/api/documents/${target?.id}`),
    ).rejects.toMatchObject({ name: "ApiError", status: 404 });
  });

  it("scores POST search hits with citations", async () => {
    const chunks = await mockTransport.request<{ citation: { filename: string; score: number } }[]>(
      "/api/documents/search",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: "riser bracket hairline cracks", top_k: 3 }),
      },
    );
    expect(chunks.length).toBeGreaterThan(0);
    expect(chunks.length).toBeLessThanOrEqual(3);
    expect(chunks[0]?.citation.filename).toContain("INS-2024-07");
    expect(chunks[0]?.citation.score).toBeGreaterThan(0);
  });

  it("honours the audit limit and type filter", async () => {
    const limited = await mockTransport.request<unknown[]>("/api/audit?limit=2");
    expect(limited).toHaveLength(2);
    const all = await mockTransport.request<{ type: string }[]>("/api/audit?limit=200");
    const first = all[0]?.type;
    expect(typeof first).toBe("string");
    const filtered = await mockTransport.request<{ type: string }[]>(
      `/api/audit?limit=200&type=${encodeURIComponent(first ?? "")}`,
    );
    expect(filtered.length).toBeGreaterThan(0);
    expect(filtered.every((event) => event.type === first)).toBe(true);
  });

  it("cancels a task through POST /tasks/:id/cancel", async () => {
    await mockTransport.request("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload("stand by")),
    });
    const [created] = await mockTransport.request<Task[]>("/api/tasks?limit=1");
    expect(created).toBeDefined();
    await mockTransport.request(`/api/tasks/${created?.id}/cancel`, { method: "POST" });
    const after = await mockTransport.request<Task>(`/api/tasks/${created?.id}`);
    expect(after.status).toBe("cancelled");
  });
});

describe("mock chat stream", () => {
  it("plays the full document scenario and replays it on reconnect", async () => {
    const events: AgentEvent[] = [];
    await mockTransport.chatStream(
      payload("Read the attached inspection report and draft an approval note."),
      (event) => events.push(event),
    );

    const types = typesOf(events);
    expect(types[0]).toBe("task_created");
    expect(types[types.length - 1]).toBe("done");
    for (const expected of ["plan", "step_start", "tool_call", "tool_result", "token", "artifact"]) {
      expect(types).toContain(expected);
    }

    const plan = events.find((event) => event.type === "plan");
    expect(plan?.data.model_id).toBe("qwen2.5:3b-instruct");
    expect(plan?.data.capability).toBe("chat");

    const search = events.find(
      (event) => event.type === "tool_result" && event.data.tool === "doc_search",
    );
    expect(Array.isArray(search?.data.citations)).toBe(true);
    expect((search?.data.citations as unknown[]).length).toBe(3);

    const artifact = events.find((event) => event.type === "artifact");
    expect(artifact?.data.filename).toBe("Approval-Note-Unit12.docx");

    const answer = events
      .filter((event) => event.type === "token")
      .map((event) => String(event.data.text))
      .join("");
    expect(answer).toContain("Approval note ready");
    expect(answer).toContain("Riser bracket");

    const done = events.at(-1);
    expect(done?.data.artifacts).toEqual(["Approval-Note-Unit12.docx"]);

    const created = events[0];
    const taskId = String(created?.data.task_id);
    const stored = await mockTransport.request<Task>(`/api/tasks/${taskId}`);
    expect(stored.status).toBe("done");
    expect(stored.artifacts).toHaveLength(1);

    const replay: AgentEvent[] = [];
    await mockTransport.taskEventsStream(taskId, (event) => replay.push(event));
    expect(replay).toHaveLength(events.length);
    expect(typesOf(replay)).toEqual(types);
  }, 20000);

  it("auto-selects the coder model for code tasks", async () => {
    const events: AgentEvent[] = [];
    await mockTransport.chatStream(
      payload("Write a python script that reconciles the Q3 utilisation CSV"),
      (event) => events.push(event),
    );

    const plan = events.find((event) => event.type === "plan");
    expect(plan?.data.model_id).toBe("qwen2.5-coder:3b");
    expect(plan?.data.capability).toBe("code");

    const run = events.find(
      (event) => event.type === "tool_result" && event.data.tool === "code_exec",
    );
    expect(run?.data.exit_code).toBe(0);

    const artifact = events.find((event) => event.type === "artifact");
    expect(artifact?.data.filename).toBe("analyze_units.py");
    expect(events.at(-1)?.type).toBe("done");
  }, 20000);

  it("keeps an explicitly requested model", async () => {
    const events: AgentEvent[] = [];
    await mockTransport.chatStream(payload("Draft a summary note.", "qwen2.5:1.5b-instruct"), (event) =>
      events.push(event),
    );
    const plan = events.find((event) => event.type === "plan");
    expect(plan?.data.model_id).toBe("qwen2.5:1.5b-instruct");
  }, 20000);

  it("stops on abort and marks the task cancelled", async () => {
    const events: AgentEvent[] = [];
    const controller = new AbortController();
    const running = mockTransport.chatStream(
      payload("Read the inspection report"),
      (event) => events.push(event),
      controller.signal,
    );
    setTimeout(() => controller.abort(), 300);
    await expect(running).rejects.toMatchObject({ name: "AbortError" });

    const created = events[0];
    const taskId = String(created?.data.task_id);
    const stored = await mockTransport.request<Task>(`/api/tasks/${taskId}`);
    expect(stored.status).toBe("cancelled");
  }, 20000);

  it("rejects replay for an unknown task", async () => {
    await expect(mockTransport.taskEventsStream("task-nope", () => undefined)).rejects.toMatchObject({
      status: 404,
    });
  });
});
