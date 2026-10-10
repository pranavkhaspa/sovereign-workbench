import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import type { AuditEvent, EgressStatus } from "../api/types";
import { SovereigntyPanel } from "../components/SovereigntyPanel";
import { formatTime } from "../lib/format";

function queryError(error: unknown): string | null {
  return error instanceof Error ? error.message : error ? "Request failed" : null;
}

export function SovereigntyPage(): JSX.Element {
  const [filter, setFilter] = useState("");
  const [eventType, setEventType] = useState("all");
  const egress = useQuery<EgressStatus>({
    queryKey: ["egress"],
    queryFn: api.egress,
    refetchInterval: 3000,
  });
  const audit = useQuery<AuditEvent[]>({
    queryKey: ["audit"],
    queryFn: api.audit,
    refetchInterval: 5000,
  });

  const eventTypes = useMemo(
    () => Array.from(new Set((audit.data ?? []).map((event) => event.type))).sort(),
    [audit.data],
  );
  const visibleEvents = useMemo(
    () =>
      (audit.data ?? []).filter((event) => {
        const matchesType = eventType === "all" || event.type === eventType;
        const haystack = `${event.type} ${event.actor} ${event.detail}`.toLowerCase();
        return matchesType && haystack.includes(filter.toLowerCase());
      }),
    [audit.data, eventType, filter],
  );

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <div className="section-kicker">SECURITY / OBSERVABILITY</div>
          <h1>Sovereignty center</h1>
          <p>A live, auditable view of the boundary around local inference and data.</p>
        </div>
        <div className="page-heading-meta">
          <span className="metric-label">AUDIT EVENTS</span>
          <strong>{audit.data?.length ?? "—"}</strong>
          <span>rolling local log</span>
        </div>
      </div>
      <SovereigntyPanel
        status={egress.data}
        loading={egress.isPending || egress.isFetching}
        error={queryError(egress.error)}
        onRefresh={() => void egress.refetch()}
      />
      {queryError(audit.error) && (
        <div className="panel-message panel-message-error">
          <span>!</span>Could not load audit log: {queryError(audit.error)}
        </div>
      )}
      <section className="panel audit-panel">
        <div className="panel-heading">
          <div>
            <div className="section-kicker">APPEND-ONLY EVENT LOG</div>
            <h2>Audit events</h2>
          </div>
          <span className="muted-text">{visibleEvents.length} visible</span>
        </div>
        <div className="audit-filters">
          <div className="search-input-wrap">
            <span>⌕</span>
            <input
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="Filter actor or detail..."
              aria-label="Filter audit events"
            />
            <button type="button" onClick={() => setFilter("")} disabled={!filter}>
              Clear
            </button>
          </div>
          <select
            className="select-control audit-select"
            value={eventType}
            onChange={(event) => setEventType(event.target.value)}
          >
            <option value="all">All event types</option>
            {eventTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
        {audit.isPending ? (
          <div className="loading-row">
            <span className="button-spinner" /> Loading audit trail...
          </div>
        ) : visibleEvents.length ? (
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Type</th>
                  <th>Actor</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {visibleEvents.map((event) => (
                  <tr key={event.id}>
                    <td className="mono muted-text">{formatTime(event.created_at)}</td>
                    <td>
                      <span
                        className={`audit-type audit-type-${event.type.includes("egress") ? "egress" : "default"}`}
                      >
                        {event.type}
                      </span>
                    </td>
                    <td className="mono">{event.actor}</td>
                    <td>{event.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state compact-empty">
            <span className="empty-mark">⌁</span>
            <strong>{audit.data?.length ? "No matching events" : "Audit trail is empty"}</strong>
            <span>
              {audit.data?.length
                ? "Adjust the filters to inspect another event."
                : "Local activity will be recorded here as the workbench runs."}
            </span>
          </div>
        )}
      </section>
    </div>
  );
}
