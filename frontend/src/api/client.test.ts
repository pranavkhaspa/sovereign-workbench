import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, artifactDownloadUrl } from "./client";

interface RecordedCall {
  url: string;
  init?: RequestInit;
}

let queue: (Response | Error)[] = [];
const calls: RecordedCall[] = [];

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 404 ? "Not Found" : "",
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

async function captureError(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    if (error instanceof ApiError) return error;
    throw error;
  }
  throw new Error("expected the request to fail");
}

beforeEach(() => {
  queue = [];
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: unknown, init?: RequestInit) => {
      calls.push({ url: String(input), init });
      const next = queue.shift();
      if (next instanceof Error) throw next;
      if (!next) throw new Error("fetch called more times than the test queued responses");
      return next;
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api error normalisation", () => {
  it("returns the parsed payload on success", async () => {
    queue = [jsonResponse({ status: "ok", version: "0.1.0", airgap: true })];
    await expect(api.health()).resolves.toMatchObject({ status: "ok", airgap: true });
    expect(calls[0]?.url).toBe("/api/health");
  });

  it("surfaces a FastAPI detail string", async () => {
    queue = [jsonResponse({ detail: "prompt is required" }, 422)];
    const error = await captureError(api.createTask({ prompt: "", options: {
      allow_network: false,
      write_files: false,
      run_code: false,
    } }));
    expect(error.message).toBe("prompt is required");
    expect(error.status).toBe(422);
    expect(calls[0]?.init?.method).toBe("POST");
  });

  it("surfaces a nested error envelope", async () => {
    queue = [jsonResponse({ error: { message: "model registry unavailable" } }, 503)];
    const error = await captureError(api.models());
    expect(error.message).toBe("model registry unavailable");
    expect(error.status).toBe(503);
  });

  it("falls back to a status line when the body is not JSON", async () => {
    queue = [
      {
        ok: false,
        status: 502,
        statusText: "Bad Gateway",
        json: async () => {
          throw new Error("not json");
        },
        text: async () => "<html>bad gateway</html>",
      } as unknown as Response,
    ];
    const error = await captureError(api.tasks());
    expect(error.message).toBe("502 Bad Gateway");
    expect(error.status).toBe(502);
  });

  it("wraps a network failure as status 0", async () => {
    queue = [new Error("ECONNREFUSED 127.0.0.1:8000")];
    const error = await captureError(api.egress());
    expect(error.status).toBe(0);
    expect(error.message).toMatch(/^Backend unavailable: /);
    expect(error.message).toContain("ECONNREFUSED");
  });
});

describe("api.searchDocuments", () => {
  it("POSTs to /api/documents/search", async () => {
    queue = [
      jsonResponse([
        {
          id: "chunk-1",
          text: "Riser bracket shows two hairline cracks.",
          citation: {
            document_id: "doc-ins-2024-07",
            filename: "INS-2024-07-Unit12-Inspection.pdf",
            page: 3,
            span: null,
            score: 0.91,
          },
        },
      ]),
    ];
    const chunks = await api.searchDocuments("riser bracket", 3);
    expect(chunks).toHaveLength(1);
    expect(chunks[0]?.citation.filename).toContain("INS-2024-07");
    expect(calls[0]?.url).toBe("/api/documents/search");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(calls[0]?.init?.body).toBe(JSON.stringify({ query: "riser bracket", top_k: 3 }));
  });

  it("falls back to the GET route when POST search is missing", async () => {
    queue = [jsonResponse({ detail: "Not Found" }, 404), jsonResponse([])];
    await expect(api.searchDocuments("riser bracket")).resolves.toEqual([]);
    expect(calls).toHaveLength(2);
    expect(calls[1]?.url).toBe("/api/documents/search?q=riser%20bracket&top_k=5");
    expect(calls[1]?.init?.method).toBeUndefined();
  });

  it("rethrows anything that is not a 404/405", async () => {
    queue = [jsonResponse({ detail: "index corrupted" }, 500)];
    const error = await captureError(api.searchDocuments("riser bracket"));
    expect(error.status).toBe(500);
    expect(calls).toHaveLength(1);
  });
});

describe("artifactDownloadUrl", () => {
  it("points at the backend download route", () => {
    expect(artifactDownloadUrl("art-9")).toBe("/api/artifacts/art-9/download");
  });
});
