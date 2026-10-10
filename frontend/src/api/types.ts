// API contract — mirror of backend/src/sovereign_workbench/schemas.
// Keep in lockstep with CHECKLIST.md §4. If the backend schema changes, this file
// changes in the same pull request.

export type Capability = "plan" | "chat" | "code" | "vision" | "embed";
export type Tier = "min" | "standard" | "large" | "remote";

export interface ModelInfo {
  id: string;
  label: string;
  provider: string;
  remote: boolean;
  tier: Tier;
  capabilities: Capability[];
  available: boolean;
  size_hint: string | null;
  notes: string | null;
}

export interface ModelList {
  models: ModelInfo[];
}

export interface TaskOptions {
  allow_network: boolean;
  write_files: boolean;
  run_code: boolean;
  max_steps?: number | null;
}

export interface TaskCreate {
  prompt: string;
  attachments?: string[];
  model_id?: string | null;
  options: TaskOptions;
}

export interface TaskStep {
  index: number;
  kind: string;
  title: string;
  detail: string | null;
  tool: string | null;
  args: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  ok: boolean | null;
  started_at: string | null;
  ended_at: string | null;
}

export interface Artifact {
  id: string;
  task_id: string | null;
  filename: string;
  kind: string;
  size_bytes: number;
  created_at: string;
}

export interface Task {
  id: string;
  prompt: string;
  status: "queued" | "running" | "done" | "error" | "cancelled";
  model_id: string | null;
  created_at: string;
  updated_at: string;
  steps: TaskStep[];
  artifacts: Artifact[];
  error: string | null;
}

export interface Document {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  chunk_count: number;
  status: string;
  created_at: string;
}

export interface Citation {
  document_id: string;
  filename: string;
  page: number | null;
  span: string | null;
  score: number;
}

export interface Chunk {
  id: string;
  text: string;
  citation: Citation;
}

export interface AuditEvent {
  id: string;
  type: string;
  actor: string;
  detail: string;
  data: Record<string, unknown> | null;
  created_at: string;
}

export interface EgressStatus {
  airgap: boolean;
  blocked: number;
  allowed_local: number;
  external_allowed: number;
  local_endpoints: string[];
}

export interface HealthStatus {
  status: string;
  version: string;
  airgap: boolean;
  hardware_tier: string;
  models: number;
}

export type AgentEventType =
  | "task_created"
  | "plan"
  | "step_start"
  | "tool_call"
  | "tool_result"
  | "token"
  | "artifact"
  | "done"
  | "error";

export interface AgentEvent {
  type: AgentEventType;
  task_id: string;
  at: string;
  data: Record<string, unknown>;
}
