import { artifactDownloadUrl } from "../api/client";
import type { Artifact } from "../api/types";
import { extensionOf, formatBytes, formatDate } from "../lib/format";

const ICON: Record<string, string> = {
  docx: "DOC",
  pptx: "PPT",
  xlsx: "XLS",
  code: "PY",
  text: "TXT",
  log: "LOG",
};

interface Props {
  artifacts: Artifact[];
  loading?: boolean;
  error?: string | null;
  taskId?: string | null;
}

export function ArtifactList({
  artifacts,
  loading = false,
  error = null,
  taskId = null,
}: Props): JSX.Element {
  if (loading)
    return (
      <div className="loading-row">
        <span className="button-spinner" /> Loading deliverables...
      </div>
    );
  if (error)
    return (
      <div className="panel-message panel-message-error">Could not load artifacts: {error}</div>
    );
  if (artifacts.length === 0) {
    return (
      <div className="empty-state compact-empty">
        <span className="empty-mark">▣</span>
        <strong>{taskId ? "No deliverables for this run" : "No deliverables yet"}</strong>
        <span>Generated Word, spreadsheet, presentation, code, and log files will land here.</span>
      </div>
    );
  }
  return (
    <div className="artifact-list">
      {artifacts.map((artifact) => {
        const type = ICON[artifact.kind] ?? extensionOf(artifact.filename).toUpperCase();
        return (
          <article className="artifact-card" key={artifact.id}>
            <div className="artifact-type">{type}</div>
            <div className="artifact-copy">
              <strong title={artifact.filename}>{artifact.filename}</strong>
              <span>
                {formatBytes(artifact.size_bytes)} <i>·</i> {formatDate(artifact.created_at)}
              </span>
            </div>
            <a
              className="download-link"
              href={artifactDownloadUrl(artifact.id)}
              download={artifact.filename}
              aria-label={`Download ${artifact.filename}`}
            >
              <span>↓</span> Download
            </a>
          </article>
        );
      })}
    </div>
  );
}
