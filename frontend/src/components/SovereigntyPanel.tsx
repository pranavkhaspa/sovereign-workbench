import type { EgressStatus } from "../api/types";

interface Props {
  status: EgressStatus | undefined;
  loading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
  compact?: boolean;
}

export function SovereigntyPanel({
  status,
  loading = false,
  error = null,
  onRefresh,
  compact = false,
}: Props): JSX.Element {
  const external = status?.external_allowed;
  const airgapped = status?.airgap ?? true;
  const clean = Boolean(status) && airgapped && external === 0;
  const pending = !status && !error;

  return (
    <section
      className={`sovereignty-card ${pending ? "sovereignty-pending" : clean ? "sovereignty-clean" : "sovereignty-alert"} ${compact ? "sovereignty-compact" : ""}`}
    >
      <div className="sovereignty-card-head">
        <div>
          <div className="section-kicker">SECURITY MONITOR</div>
          <h2>Network sovereignty</h2>
        </div>
        {onRefresh && (
          <button
            className="icon-button refresh-button"
            type="button"
            onClick={onRefresh}
            disabled={loading}
            aria-label="Refresh network status"
          >
            ↻
          </button>
        )}
      </div>
      <div className="sovereignty-hero">
        <div className="sovereignty-ring">
          <span>{status ? (clean ? "0" : external) : "—"}</span>
          <small>external</small>
        </div>
        <div>
          <strong>{pending ? "TELEMETRY PENDING" : clean ? "AIR-GAP ON" : "REVIEW EGRESS"}</strong>
          <p>
            {pending
              ? "Waiting for local security telemetry"
              : clean
                ? "No outbound calls observed"
                : "External network activity requires review"}
          </p>
        </div>
      </div>
      {error ? (
        <div className="panel-message panel-message-error">Monitor unavailable: {error}</div>
      ) : (
        <div className="sovereignty-metrics">
          <div>
            <span>BLOCKED ATTEMPTS</span>
            <strong>{status?.blocked ?? "—"}</strong>
          </div>
          <div>
            <span>LOCAL CALLS</span>
            <strong>{status?.allowed_local ?? "—"}</strong>
          </div>
          <div>
            <span>EXTERNAL ALLOWED</span>
            <strong className={status ? (external === 0 ? "metric-ok" : "metric-danger") : ""}>
              {external ?? "—"}
            </strong>
          </div>
        </div>
      )}
      {!compact && (
        <div className="endpoint-block">
          <span>ALLOWLISTED LOCAL ENDPOINTS</span>
          {status?.local_endpoints.length ? (
            <ul>
              {status.local_endpoints.map((endpoint) => (
                <li key={endpoint}>
                  <span className="status-dot" />
                  {endpoint}
                </li>
              ))}
            </ul>
          ) : (
            <p>Awaiting backend telemetry…</p>
          )}
        </div>
      )}
      {loading && (
        <div className="refresh-note">
          <span className="button-spinner" /> syncing telemetry
        </div>
      )}
    </section>
  );
}
