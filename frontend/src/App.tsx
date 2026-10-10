import { useEffect, useState } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { api } from "./api/client";
import type { HealthStatus } from "./api/types";
import { DocumentsPage } from "./pages/Documents";
import { ModelsPage } from "./pages/Models";
import { SovereigntyPage } from "./pages/Sovereignty";
import { WorkbenchPage } from "./pages/Workbench";
import { useSession } from "./store/useSession";

type Tab = "workbench" | "documents" | "models" | "sovereignty";

const TABS: { id: Tab; label: string; short: string }[] = [
  { id: "workbench", label: "Workbench", short: "RUN" },
  { id: "documents", label: "Knowledge base", short: "DOCS" },
  { id: "models", label: "Model registry", short: "MODELS" },
  { id: "sovereignty", label: "Sovereignty", short: "AUDIT" },
];

function queryError(error: unknown): string | null {
  return error instanceof Error ? error.message : error ? "Request failed" : null;
}

function ConnectionStatus({ health }: { health: UseQueryResult<HealthStatus> }): JSX.Element {
  if (health.isPending)
    return (
      <span className="connection-status connection-pending">
        <span className="status-dot" /> checking backend
      </span>
    );
  if (health.isError)
    return (
      <span className="connection-status connection-error">
        <span className="status-dot" /> backend offline
      </span>
    );
  return (
    <span className="connection-status">
      <span className="status-dot" /> local backend · {health.data?.hardware_tier ?? "ready"}
    </span>
  );
}

export default function App(): JSX.Element {
  const [tab, setTab] = useState<Tab>("workbench");
  const health = useQuery<HealthStatus>({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15000,
  });
  const setAirgap = useSession((state) => state.setAirgap);

  useEffect(() => {
    if (health.data) setAirgap(health.data.airgap);
  }, [health.data, setAirgap]);

  return (
    <div className="app-frame">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div>
            <div className="brand-name">
              SOVEREIGN <b>WORKBENCH</b>
            </div>
            <div className="brand-subtitle">
              ON-PREMISE INTELLIGENCE CONSOLE <span>·</span> v{health.data?.version ?? "0.1"}
            </div>
          </div>
        </div>
        <div className="topbar-right">
          <ConnectionStatus health={health} />
          <div className="operator-chip">
            <span className="operator-avatar">OP</span>
            <span>Operator</span>
            <span className="chevron">⌄</span>
          </div>
        </div>
      </header>
      <div className="workspace-frame">
        <aside className="side-rail">
          <div className="rail-label">CONTROL SURFACES</div>
          <nav aria-label="Primary navigation">
            {TABS.map((item) => (
              <button
                key={item.id}
                className={`nav-item ${tab === item.id ? "nav-item-active" : ""}`}
                type="button"
                onClick={() => setTab(item.id)}
                aria-current={tab === item.id ? "page" : undefined}
              >
                <span className={`nav-glyph nav-glyph-${item.id}`} aria-hidden="true">
                  {item.short.slice(0, 1)}
                </span>
                <span>{item.label}</span>
                {item.id === "sovereignty" && <span className="nav-live-dot" />}
              </button>
            ))}
          </nav>
          <div className="rail-footer">
            <div className="rail-label">SYSTEM POSTURE</div>
            <div
              className={`rail-posture ${health.data?.airgap === false ? "rail-posture-warning" : ""}`}
            >
              <span className="status-dot" />
              {health.isPending
                ? "CHECKING POSTURE"
                : health.data?.airgap === false
                  ? "AIR-GAP OFF"
                  : "AIR-GAP ACTIVE"}
            </div>
            <p>All inference and document processing remains inside the local workspace.</p>
          </div>
        </aside>
        <main className="main-canvas">
          <div className="mobile-page-nav">
            <label htmlFor="mobile-nav">VIEW</label>
            <select
              id="mobile-nav"
              value={tab}
              onChange={(event) => setTab(event.target.value as Tab)}
            >
              {TABS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          {tab === "workbench" && <WorkbenchPage backendError={queryError(health.error)} />}
          {tab === "documents" && <DocumentsPage />}
          {tab === "models" && <ModelsPage />}
          {tab === "sovereignty" && <SovereigntyPage />}
        </main>
      </div>
      <footer className="app-footer">
        <span>SWB / LOCAL INSTANCE</span>
        <span>POLICY: NO EXTERNAL TRANSPORT</span>
        <span>TELEMETRY: MINIMAL · AUDITABLE</span>
      </footer>
    </div>
  );
}
