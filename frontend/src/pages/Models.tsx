import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";
import type { ModelList } from "../api/types";
import { useSession } from "../store/useSession";

function queryError(error: unknown): string | null {
  return error instanceof Error ? error.message : error ? "Request failed" : null;
}

const CAPABILITY_LABELS: Record<string, string> = {
  plan: "planning",
  chat: "general",
  code: "code",
  vision: "vision",
  embed: "retrieval",
};

export function ModelsPage(): JSX.Element {
  const queryClient = useQueryClient();
  const models = useQuery<ModelList>({ queryKey: ["models"], queryFn: api.models });
  const refresh = useMutation({
    mutationFn: api.refreshModels,
    onSuccess: (data) => queryClient.setQueryData(["models"], data),
  });
  const selectedModelId = useSession((state) => state.selectedModelId);
  const setSelectedModelId = useSession((state) => state.setSelectedModelId);

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <div className="section-kicker">INFERENCE / REGISTRY</div>
          <h1>Model registry</h1>
          <p>See which local capabilities are ready and pin a route for the next run.</p>
        </div>
        <button
          className="button button-secondary"
          type="button"
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending}
        >
          {refresh.isPending ? (
            <>
              <span className="button-spinner" /> Probing local runtime
            </>
          ) : (
            <>↻ Refresh availability</>
          )}
        </button>
      </div>
      {queryError(models.error) && (
        <div className="panel-message panel-message-error">
          <span>!</span>Could not load model registry: {queryError(models.error)}
        </div>
      )}
      {refresh.error && (
        <div className="panel-message panel-message-error">
          <span>!</span>Availability refresh failed:{" "}
          {refresh.error instanceof Error ? refresh.error.message : "request failed"}
        </div>
      )}
      <section className="registry-banner panel-grid-lines">
        <div className="registry-banner-icon">◎</div>
        <div>
          <strong>Routing stays inside the sovereignty boundary</strong>
          <p>
            Auto mode chooses by capability, hardware tier, and model availability. Remote providers
            remain visible for audit but are disabled in air-gap mode.
          </p>
        </div>
        <div className="registry-count">
          <b>{models.data?.models.filter((model) => model.available).length ?? "—"}</b>
          <span>ready routes</span>
        </div>
      </section>
      {models.isPending ? (
        <div className="panel loading-row">
          <span className="button-spinner" /> Loading registry...
        </div>
      ) : models.data?.models.length ? (
        <section className="model-grid">
          {models.data.models.map((model) => {
            const selected = selectedModelId === model.id;
            const selectable = model.available && !model.remote;
            return (
              <article
                className={`model-card ${selected ? "model-card-selected" : ""} ${!selectable ? "model-card-disabled" : ""}`}
                key={model.id}
              >
                <div className="model-card-head">
                  <span
                    className={`availability-indicator ${model.available ? "available" : "unavailable"}`}
                  />
                  <span className="model-tier">{model.tier}</span>
                  {model.remote && <span className="remote-label">remote</span>}
                </div>
                <h2>{model.label}</h2>
                <code>{model.id}</code>
                <div className="capability-list">
                  {model.capabilities.map((capability) => (
                    <span key={capability}>{CAPABILITY_LABELS[capability] ?? capability}</span>
                  ))}
                </div>
                <div className="model-card-meta">
                  <span>{model.provider}</span>
                  <span>{model.size_hint ?? "size unknown"}</span>
                </div>
                {model.notes && <p className="model-notes">{model.notes}</p>}
                <button
                  className={`button ${selected ? "button-selected" : "button-secondary"} button-small model-select-button`}
                  type="button"
                  disabled={!selectable}
                  onClick={() => setSelectedModelId(selected ? null : model.id)}
                >
                  {selected
                    ? "Selected for runs"
                    : selectable
                      ? "Use this model"
                      : model.remote
                        ? "Blocked by air-gap"
                        : "Unavailable"}
                </button>
              </article>
            );
          })}
        </section>
      ) : (
        <div className="panel empty-state">
          <span className="empty-mark">◎</span>
          <strong>No models registered</strong>
          <span>Add a local provider to the backend registry, then refresh availability.</span>
        </div>
      )}
      <section className="panel model-routing-note">
        <div className="section-kicker">HOW ROUTING WORKS</div>
        <div className="routing-steps">
          <div>
            <span>01</span>
            <strong>Classify</strong>
            <p>Prompt signals identify chat, code, vision, or retrieval work.</p>
          </div>
          <div>
            <span>02</span>
            <strong>Constrain</strong>
            <p>Air-gap and hardware policy remove unsafe or oversized routes.</p>
          </div>
          <div>
            <span>03</span>
            <strong>Execute</strong>
            <p>The selected local provider produces the traceable result.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
