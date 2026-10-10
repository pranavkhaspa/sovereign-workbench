import { ApiError } from "./errors";
import { transport } from "./transport";
import type {
  AgentEvent,
  Artifact,
  AuditEvent,
  Chunk,
  Document,
  EgressStatus,
  HealthStatus,
  ModelInfo,
  ModelList,
  Task,
  TaskCreate,
} from "./types";

export { ApiError };

export interface AuditQuery {
  limit?: number;
  type?: string;
}

export const api = {
  health: () => transport.request<HealthStatus>("/api/health"),
  egress: () => transport.request<EgressStatus>("/api/health/egress"),
  models: () => transport.request<ModelList>("/api/models"),
  model: (id: string) => transport.request<ModelInfo>(`/api/models/${encodeURIComponent(id)}`),
  refreshModels: () => transport.request<ModelList>("/api/models/refresh", { method: "POST" }),
  tasks: () => transport.request<Task[]>("/api/tasks?limit=50"),
  task: (id: string, signal?: AbortSignal) =>
    transport.request<Task>(`/api/tasks/${encodeURIComponent(id)}`, { signal }),
  createTask: (payload: TaskCreate) =>
    transport.request<Task>("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  cancelTask: (id: string) =>
    transport.request<{ ok: boolean }>(`/api/tasks/${encodeURIComponent(id)}/cancel`, {
      method: "POST",
    }),
  documents: () => transport.request<Document[]>("/api/documents"),
  document: (id: string) =>
    transport.request<Document>(`/api/documents/${encodeURIComponent(id)}`),
  deleteDocument: (id: string) =>
    transport.request<{ ok: boolean }>(`/api/documents/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
  searchDocuments: async (query: string, topK = 5): Promise<Chunk[]> => {
    try {
      return await transport.request<Chunk[]>("/api/documents/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: topK }),
      });
    } catch (error) {
      const notSupported = error instanceof ApiError && (error.status === 404 || error.status === 405);
      if (!notSupported) throw error;
      return transport.request<Chunk[]>(
        `/api/documents/search?q=${encodeURIComponent(query)}&top_k=${topK}`,
      );
    }
  },
  documentSearch: (query: string, topK = 5) => api.searchDocuments(query, topK),
  artifacts: (taskId?: string) =>
    transport.request<Artifact[]>(
      taskId ? `/api/artifacts?task_id=${encodeURIComponent(taskId)}` : "/api/artifacts",
    ),
  artifact: (id: string) =>
    transport.request<Artifact>(`/api/artifacts/${encodeURIComponent(id)}`),
  audit: ({ limit = 200, type }: AuditQuery = {}) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (type) params.set("type", type);
    return transport.request<AuditEvent[]>(`/api/audit?${params.toString()}`);
  },
};

export async function uploadDocument(
  file: File,
): Promise<{ document_id: string; chunks: number; status: string }> {
  return transport.upload(file);
}

export function artifactDownloadUrl(id: string): string {
  return transport.downloadUrl(id);
}

export function streamTask(
  payload: TaskCreate,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return transport.chatStream(payload, onEvent, signal);
}

export function streamTaskEvents(
  taskId: string,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return transport.taskEventsStream(taskId, onEvent, signal);
}
