import { ApiError } from "./errors";
import { mockTransport } from "./mock";
import { readSseStream } from "./sse";
import type { AgentEvent, TaskCreate } from "./types";

export const USE_MOCK = (import.meta.env.VITE_USE_MOCK ?? "").toLowerCase() === "true";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export interface UploadResult {
  document_id: string;
  chunks: number;
  status: string;
}

export interface Transport {
  request<T>(path: string, init?: RequestInit): Promise<T>;
  chatStream(
    payload: TaskCreate,
    onEvent: (event: AgentEvent) => void,
    signal?: AbortSignal,
  ): Promise<void>;
  taskEventsStream(
    taskId: string,
    onEvent: (event: AgentEvent) => void,
    signal?: AbortSignal,
  ): Promise<void>;
  upload(file: File): Promise<UploadResult>;
  downloadUrl(id: string): string;
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
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function openStream(
  path: string,
  init: RequestInit,
  signal: AbortSignal | undefined,
  unavailable: string,
): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), { ...init, signal });
  } catch (error) {
    if (signal?.aborted) throw new DOMException("Stream stopped", "AbortError");
    const message = error instanceof Error ? error.message : "network request failed";
    throw new ApiError(`${unavailable}: ${message}`, 0);
  }
  if (!response.ok || !response.body) {
    const message = response.ok
      ? "The backend returned an empty stream"
      : `${response.status} ${response.statusText}`;
    throw new ApiError(message, response.status);
  }
  return response;
}

async function chatStream(
  payload: TaskCreate,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await openStream(
    "/api/chat",
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(payload),
    },
    signal,
    "Stream unavailable",
  );
  await readSseStream(response, onEvent);
}

async function taskEventsStream(
  taskId: string,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await openStream(
    `/api/tasks/${encodeURIComponent(taskId)}/events`,
    { method: "GET", headers: { Accept: "text/event-stream" } },
    signal,
    "Replay unavailable",
  );
  await readSseStream(response, onEvent);
}

async function upload(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResult>("/api/documents", { method: "POST", body: form });
}

export const fetchTransport: Transport = {
  request,
  chatStream,
  taskEventsStream,
  upload,
  downloadUrl: (id) => apiUrl(`/api/artifacts/${encodeURIComponent(id)}/download`),
};

export const transport: Transport = USE_MOCK ? mockTransport : fetchTransport;
