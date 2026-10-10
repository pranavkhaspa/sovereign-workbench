import { useEffect, useRef, useState } from "react";

import { formatTime } from "../lib/format";
import type { StreamState, TimelineEntry } from "../store/useWorkbench";

const EVENT_META: Record<string, { icon: string; label: string; tone: string }> = {
  task_created: { icon: "＋", label: "accepted", tone: "timeline-accent" },
  plan: { icon: "≡", label: "plan", tone: "timeline-accent" },
  step_start: { icon: "◇", label: "step", tone: "timeline-neutral" },
  tool_call: { icon: "↗", label: "tool call", tone: "timeline-warn" },
  tool_result: { icon: "✓", label: "result", tone: "timeline-ok" },
  artifact: { icon: "▣", label: "artifact", tone: "timeline-accent" },
  done: { icon: "◆", label: "complete", tone: "timeline-ok" },
  error: { icon: "!", label: "error", tone: "timeline-danger" },
};

function detailFor(entry: TimelineEntry): string | null {
  if (entry.detail) return entry.detail;
  const data = { ...entry.data };
  delete data.task_id;
  delete data.at;
  if (Object.keys(data).length === 0) return null;
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return null;
  }
}

function streamLabel(streamState: StreamState): string {
  switch (streamState) {
    case "connecting":
      return "opening stream";
    case "streaming":
      return "live execution";
    case "complete":
      return "run complete";
    case "stopped":
      return "stopped by operator";
    case "error":
      return "stream error";
    case "disconnected":
      return "stream disconnected";
    default:
      return "awaiting task";
  }
}

export function AgentTimeline({
  entries,
  streamState,
}: {
  entries: TimelineEntry[];
  streamState: StreamState;
}): JSX.Element {
  const [expanded, setExpanded] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [entries.length]);

  return (
    <div className="timeline-wrap">
      <div className="timeline-status">
        <span className={`stream-indicator stream-${streamState}`} />
        <span>{streamLabel(streamState)}</span>
        <span className="timeline-count">{entries.length.toString().padStart(2, "0")} events</span>
      </div>
      {entries.length === 0 ? (
        <div className="empty-state compact-empty">
          <span className="empty-mark">◌</span>
          <strong>Trajectory is clear</strong>
          <span>When a task runs, each planning step and local tool call will appear here.</span>
        </div>
      ) : (
        <ol className="timeline-list">
          {entries.map((entry) => {
            const meta = EVENT_META[entry.type] ?? {
              icon: "·",
              label: entry.type,
              tone: "timeline-neutral",
            };
            const detail = detailFor(entry);
            const isExpanded = expanded === entry.id;
            const expandable = Boolean(detail);
            return (
              <li className={`timeline-entry ${meta.tone}`} key={entry.id}>
                <span className="timeline-line" aria-hidden="true" />
                <span className="timeline-icon" aria-hidden="true">
                  {meta.icon}
                </span>
                <div className="timeline-entry-body">
                  <div className="timeline-entry-head">
                    <span className="timeline-event-label">{meta.label}</span>
                    <time>{formatTime(entry.at)}</time>
                  </div>
                  <div className="timeline-entry-title">{entry.label}</div>
                  {detail && (
                    <button
                      type="button"
                      className={`timeline-detail ${isExpanded ? "timeline-detail-open" : ""}`}
                      onClick={() => setExpanded(isExpanded ? null : entry.id)}
                      aria-expanded={isExpanded}
                      disabled={!expandable}
                    >
                      <span className="detail-caret">{isExpanded ? "⌄" : "›"}</span>
                      <span
                        className={
                          entry.type === "tool_call" || entry.type === "tool_result"
                            ? "mono detail-preview"
                            : "detail-preview"
                        }
                      >
                        {detail}
                      </span>
                    </button>
                  )}
                  {isExpanded && detail && <pre className="timeline-detail-expanded">{detail}</pre>}
                </div>
              </li>
            );
          })}
          <div ref={endRef} />
        </ol>
      )}
    </div>
  );
}
