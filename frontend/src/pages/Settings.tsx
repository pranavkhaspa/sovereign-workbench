import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import { API_BASE, USE_MOCK } from "../api/transport";
import type { EgressStatus, HealthStatus, ModelList } from "../api/types";
import { Badge, Button, Card, CopyButton, Textarea, useToast } from "../components/ui";
import { getTheme, setTheme, type Theme } from "../lib/theme";

const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: "Ctrl / ⌘ + Enter", action: "Run the task (or stop it while streaming)" },
  { keys: "/", action: "Focus the task composer" },
  { keys: "Esc", action: "Stop the running stream" },
  { keys: "Ctrl / ⌘ + Shift + T", action: "Show or hide the execution timeline" },
  { keys: "Ctrl / ⌘ + Shift + S", action: "Jump to the sovereignty panel" },
];

function Row({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="settings-row">
      <span className="settings-label">{label}</span>
      <span className="settings-value mono">{value}</span>
    </div>
  );
}

export function SettingsPage(): JSX.Element {
  const toast = useToast();
  const [theme, setThemeState] = useState<Theme>(getTheme);
  const health = useQuery<HealthStatus>({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15000,
  });
  const egress = useQuery<EgressStatus>({ queryKey: ["egress"], queryFn: api.egress });
  const models = useQuery<ModelList>({ queryKey: ["models"], queryFn: api.models });

  const applyTheme = (next: Theme): void => {
    setTheme(next);
    setThemeState(next);
    toast(next === "light" ? "Light theme applied" : "Dark theme applied", "ok");
  };

  const buildDiagnostic = (): string =>
    JSON.stringify(
      {
        captured_at: new Date().toISOString(),
        ui: {
          api_base: API_BASE || "(same origin)",
          mock_transport: USE_MOCK,
          theme,
        },
        health: health.data ?? null,
        egress: egress.data ?? null,
        models:
          models.data?.models.map((model) => ({
            id: model.id,
            tier: model.tier,
            provider: model.provider,
            remote: model.remote,
            available: model.available,
            capabilities: model.capabilities,
          })) ?? [],
      },
      null,
      2,
    );

  const copyDiagnostics = async (): Promise<void> => {
    const payload = buildDiagnostic();
    try {
      await navigator.clipboard.writeText(payload);
      toast("Diagnostic bundle copied to the clipboard", "ok");
    } catch {
      toast("Clipboard unavailable — the bundle is shown below", "danger");
    }
  };

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <div className="section-kicker">CONFIGURATION / LOCAL ONLY</div>
          <h1>Settings</h1>
          <p>Read-only runtime summary for this instance. No secrets are ever exposed here.</p>
        </div>
        <div className="page-heading-meta">
          <span className="metric-label">THEME</span>
          <strong>{theme.toUpperCase()}</strong>
          <span>stored on this device</span>
        </div>
      </div>

      <div className="settings-grid">
        <Card kicker="APPEARANCE" title="Theme">
          <div className="settings-row">
            <span className="settings-label">Colour scheme</span>
            <span className="inline-flex gap-2">
              <Button
                variant={theme === "dark" ? "primary" : "secondary"}
                onClick={() => applyTheme("dark")}
              >
                Dark
              </Button>
              <Button
                variant={theme === "light" ? "primary" : "secondary"}
                onClick={() => applyTheme("light")}
              >
                Light
              </Button>
            </span>
          </div>
          <p className="settings-note">
            The industrial console is dark by default; light mode is a high-contrast variant for
            printed screenshots and bright rooms.
          </p>
        </Card>

        <Card kicker="RUNTIME" title="Connection">
          <Row label="API base" value={API_BASE || "(same origin · dev proxy)"} />
          <Row label="Mock transport" value={USE_MOCK ? "ON (VITE_USE_MOCK=true)" : "off"} />
          <Row label="Backend version" value={health.data?.version ?? "—"} />
          <Row label="Hardware tier" value={health.data?.hardware_tier ?? "—"} />
          <Row label="Air-gap" value={health.data?.airgap === false ? "OFF" : "ON"} />
          <Row
            label="Local endpoints"
            value={egress.data?.local_endpoints.join(" · ") ?? "—"}
          />
          <div className="settings-row">
            <span className="settings-label">Models ready</span>
            <span className="inline-flex gap-2">
              <Badge tone={health.data?.models_ready ? "ok" : "warn"}>
                {health.data?.models_ready ? "ready" : "not ready"}
              </Badge>
              <Badge tone="accent">{models.data?.models.length ?? 0} registered</Badge>
            </span>
          </div>
        </Card>

        <Card
          kicker="DIAGNOSTICS"
          title="Copy diagnostic bundle"
          action={
            <span className="inline-flex gap-2">
              <CopyButton value={buildDiagnostic()} label="Copy JSON" />
              <Button variant="secondary" onClick={() => void copyDiagnostics()}>
                Copy to clipboard
              </Button>
            </span>
          }
        >
          <Textarea
            readOnly
            rows={8}
            aria-label="Diagnostic bundle"
            value={buildDiagnostic()}
            className="text-[11px]"
          />
          <p className="settings-note">
            Contains the health payload, egress counters and the model registry. No keys, no
            document contents.
          </p>
        </Card>

        <Card kicker="KEYBOARD" title="Shortcuts">
          <ul className="settings-shortcuts">
            {SHORTCUTS.map((shortcut) => (
              <li key={shortcut.keys}>
                <kbd>{shortcut.keys}</kbd>
                <span>{shortcut.action}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
