import type {
  Artifact,
  AuditEvent,
  Chunk,
  Document,
  EgressStatus,
  HealthStatus,
  ModelList,
  Task,
  TaskCreate,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

async function getErrorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "detail" in body) {
      const detail = body.detail;
      if (typeof detail === "string") return detail;
    }
    if (typeof body === "object" && body !== null && "error" in body) {
      const error = body.error;
      if (typeof error === "object" && error !== null && "message" in error) {
        const message = error.message;
        if (typeof message === "string") return message;
      }
    }
  } catch {
    // The server may return an empty or non-JSON error body.
  }
  return `${response.status} ${response.statusText || "request failed"}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), init);
  } catch (error) {
    const message = error instanceof Error ? error.message : "network request failed";
    throw new ApiError(`Backend unavailable: ${message}`, 0);
  }
  if (!response.ok) {
    throw new ApiError(await getErrorMessage(response), response.status);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthStatus>("/api/health"),
  egress: () => request<EgressStatus>("/api/health/egress"),
  models: () => request<ModelList>("/api/models"),
  refreshModels: () => request<ModelList>("/api/models/refresh", { method: "POST" }),
  tasks: () => request<Task[]>("/api/tasks?limit=50"),
  task: (id: string, signal?: AbortSignal) =>
    request<Task>(`/api/tasks/${encodeURIComponent(id)}`, { signal }),
  createTask: (payload: TaskCreate) =>
    request<Task>("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  documents: () => request<Document[]>("/api/documents"),
  documentSearch: (query: string, topK = 5) =>
    request<Chunk[]>(`/api/documents/search?q=${encodeURIComponent(query)}&top_k=${topK}`),
  artifacts: (taskId?: string) =>
    request<Artifact[]>(
      taskId ? `/api/artifacts?task_id=${encodeURIComponent(taskId)}` : "/api/artifacts",
    ),
  audit: () => request<AuditEvent[]>("/api/audit?limit=200"),
};

export async function uploadDocument(
  file: File,
): Promise<{ document_id: string; chunks: number; status: string }> {
  const form = new FormData();
  form.append("file", file);
  return request<{ document_id: string; chunks: number; status: string }>("/api/documents", {
    method: "POST",
    body: form,
  });
}

export function artifactDownloadUrl(id: string): string {
  return apiUrl(`/api/artifacts/${encodeURIComponent(id)}/download`);
}
