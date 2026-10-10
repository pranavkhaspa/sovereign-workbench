import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";
import type { Artifact, Document, ModelList, Task, TaskOptions } from "../api/types";
import { AgentTimeline } from "../components/AgentTimeline";
import { ArtifactList } from "../components/ArtifactList";
import { Composer } from "../components/Composer";
import { SovereigntyPanel } from "../components/SovereigntyPanel";
import { formatDate, formatTime, titleCase } from "../lib/format";
import { useWorkbench } from "../store/useWorkbench";

interface Props {
  backendError?: string | null;
}

function errorMessage(error: unknown): string | null {
  return error instanceof Error ? error.message : error ? "Request failed" : null;
}

function QueryNotice({ message }: { message: string }): JSX.Element {
  return (
    <div className="panel-message panel-message-error">
      <span>!</span>
      {message}
    </div>
  );
}

function AnswerPanel({
  answer,
  running,
  error,
}: {
  answer: string;
  running: boolean;
  error: string | null;
}): JSX.Element {
  return (
    <section className="answer-panel">
      <div className="panel-heading">
        <div>
          <div className="section-kicker">OUTPUT / GROUNDED RESPONSE</div>
          <h2>Working answer</h2>
        </div>
        <span className={`output-state ${running ? "output-state-live" : ""}`}>
          <span className="status-dot" />{" "}
          {running ? "generating" : answer ? "local result" : "standby"}
        </span>
      </div>
      {error && (
        <div className="answer-error">
          <strong>Run interrupted</strong>
          <span>{error}</span>
        </div>
      )}
      {answer ? (
        <div className="answer-copy">
          {answer}
          {running && <span className="stream-cursor" />}
        </div>
      ) : (
        <div className="empty-state answer-empty">
          <span className="empty-mark">✦</span>
          <strong>
            {running ? "Building a grounded response" : "Your deliverable starts here"}
          </strong>
          <span>
            {running
              ? "Tokens will appear as the local model completes the run."
              : "Run a task to see the final answer, evidence, and artifact references."}
          </span>
        </div>
      )}
    </section>
  );
}

function RecentRuns({
  tasks,
  loading,
  error,
}: {
  tasks: Task[];
  loading: boolean;
  error: string | null;
}): JSX.Element {
  return (
    <section className="panel recent-runs-panel">
      <div className="panel-heading panel-heading-tight">
        <div>
          <div className="section-kicker">RECENT ACTIVITY</div>
          <h2>Run ledger</h2>
        </div>
        <span className="muted-text">local only</span>
      </div>
      {loading && (
        <div className="loading-row">
          <span className="button-spinner" /> Loading history...
        </div>
      )}
      {error && <QueryNotice message={error} />}
      {!loading && !error && tasks.length === 0 && (
        <div className="empty-state compact-empty">
          <span className="empty-mark">⌁</span>
          <strong>No prior runs</strong>
          <span>Completed tasks will remain available in the local ledger.</span>
        </div>
      )}
      {tasks.length > 0 && (
        <div className="run-ledger">
          {tasks.slice(0, 5).map((task) => (
            <div className="run-ledger-row" key={task.id}>
              <span className={`run-status run-status-${task.status}`} />
              <div className="run-ledger-copy">
                <strong>{task.prompt}</strong>
                <span>
                  {formatDate(task.created_at)} · {task.steps.length} events
                </span>
              </div>
              <span className="run-status-label">{titleCase(task.status)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function WorkbenchPage({ backendError = null }: Props): JSX.Element {
  const queryClient = useQueryClient();
  const { running, streamState, taskId, answer, timeline, error, run, reconnect, stop } =
    useWorkbench();
  const models = useQuery<ModelList>({
    queryKey: ["models"],
    queryFn: api.models,
    staleTime: 15000,
  });
  const documents = useQuery<Document[]>({
    queryKey: ["documents"],
    queryFn: api.documents,
    staleTime: 10000,
  });
  const artifacts = useQuery<Artifact[]>({
    queryKey: ["artifacts", taskId],
    queryFn: () => api.artifacts(taskId ?? undefined),
    refetchInterval: running ? 2500 : false,
  });
  const egress = useQuery({ queryKey: ["egress"], queryFn: api.egress, refetchInterval: 5000 });
  const tasks = useQuery<Task[]>({
    queryKey: ["tasks"],
    queryFn: api.tasks,
    refetchInterval: running ? 5000 : false,
  });

  useEffect(() => {
    if (!running && taskId) {
      void queryClient.invalidateQueries({ queryKey: ["artifacts", taskId] });
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
    }
  }, [queryClient, running, taskId]);

  const handleSubmit = (
    prompt: string,
    modelId: string | null,
    options: TaskOptions,
    attachments: string[],
  ) => {
    void run({ prompt, model_id: modelId, options, attachments }).then(() => {
      void queryClient.invalidateQueries({ queryKey: ["artifacts"] });
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
    });
  };

  const modelError = errorMessage(models.error);
  const documentError = errorMessage(documents.error);
  const artifactError = errorMessage(artifacts.error);

  return (
    <div className="workbench-layout">
      <div className="page-heading">
        <div>
          <div className="section-kicker">WORKSPACE / ACTIVE SESSION</div>
          <h1>Agent workbench</h1>
          <p>Turn sensitive local knowledge into a verifiable deliverable.</p>
        </div>
        <div className="page-heading-meta">
          <span className="metric-label">CURRENT RUN</span>
          <strong>{taskId ? taskId.slice(0, 8).toUpperCase() : "—"}</strong>
          <span>{formatTime(new Date().toISOString())} IST</span>
        </div>
      </div>
      {backendError && <QueryNotice message={`Backend connection issue: ${backendError}`} />}
      {modelError && <QueryNotice message={`Model registry unavailable: ${modelError}`} />}
      {documentError && <QueryNotice message={`Knowledge base unavailable: ${documentError}`} />}

      <Composer
        models={models.data?.models ?? []}
        documents={documents.data ?? []}
        running={running}
        disabled={Boolean(backendError)}
        onDocumentsUploaded={() => void queryClient.invalidateQueries({ queryKey: ["documents"] })}
        onSubmit={handleSubmit}
      />

      {(running || streamState === "disconnected") && (
        <div className="run-control-banner">
          <span>
            <span className={`stream-indicator stream-${streamState}`} />
            {streamState === "disconnected"
              ? "Live stream lost · task state can be recovered"
              : `Local agent is executing · ${streamState}`}
          </span>
          {streamState === "disconnected" ? (
            <button
              className="button button-secondary button-small"
              type="button"
              onClick={() => void reconnect()}
            >
              ↻ Reconnect
            </button>
          ) : (
            <button className="button button-danger button-small" type="button" onClick={stop}>
              Stop stream
            </button>
          )}
        </div>
      )}

      <div className="workbench-columns">
        <div className="workbench-primary">
          <AnswerPanel answer={answer} running={running} error={error} />
          <section className="panel timeline-panel">
            <div className="panel-heading panel-heading-tight">
              <div>
                <div className="section-kicker">AGENT TRACE / SSE</div>
                <h2>Execution timeline</h2>
              </div>
              <span className="mono muted-text">
                {taskId ? taskId.slice(0, 12) : "NO ACTIVE TASK"}
              </span>
            </div>
            <AgentTimeline entries={timeline} streamState={streamState} />
          </section>
          <section className="panel artifacts-panel">
            <div className="panel-heading panel-heading-tight">
              <div>
                <div className="section-kicker">DELIVERABLES / LOCAL FILES</div>
                <h2>Artifacts</h2>
              </div>
              <span className="muted-text">{artifacts.data?.length ?? 0} files</span>
            </div>
            <ArtifactList
              artifacts={artifacts.data ?? []}
              loading={artifacts.isPending}
              error={artifactError}
              taskId={taskId}
            />
          </section>
        </div>
        <aside className="workbench-aside">
          <SovereigntyPanel
            status={egress.data}
            loading={egress.isPending || egress.isFetching}
            error={errorMessage(egress.error)}
            compact
            onRefresh={() => void egress.refetch()}
          />
          <section className="panel route-panel">
            <div className="section-kicker">MODEL ROUTER</div>
            <div className="route-title">
              <span className="route-pulse" />
              <strong>Capability-aware routing</strong>
            </div>
            <p>The router selects a local model by task type, hardware tier, and availability.</p>
            <div className="route-stats">
              <span>
                <b>
                  {models.data?.models.filter((model) => model.available && !model.remote).length ??
                    "—"}
                </b>{" "}
                local ready
              </span>
              <span>
                <b>{documents.data?.length ?? "—"}</b> indexed docs
              </span>
            </div>
          </section>
          <RecentRuns
            tasks={tasks.data ?? []}
            loading={tasks.isPending}
            error={errorMessage(tasks.error)}
          />
        </aside>
      </div>
    </div>
  );
}
