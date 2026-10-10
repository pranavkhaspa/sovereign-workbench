import { artifactDownloadUrl } from "../api/client";
import type { Artifact } from "../api/types";
import { extensionOf, formatBytes, formatDate } from "../lib/format";

export interface DocPreviewProps {
  artifact: Artifact;
}

const BINARY_KINDS = new Set(["docx", "pptx", "xlsx", "pdf"]);

export function DocPreview({ artifact }: DocPreviewProps): JSX.Element {
  const extension = extensionOf(artifact.filename).toUpperCase() || artifact.kind.toUpperCase();

  if (!BINARY_KINDS.has(artifact.kind)) {
    return (
      <div className="doc-preview">
        <p className="doc-preview-note">
          No readable preview for this file type. Download it to open it locally.
        </p>
        <a
          className="button button-secondary button-small"
          href={artifactDownloadUrl(artifact.id)}
          download={artifact.filename}
        >
          <span>↓</span> Download {artifact.filename}
        </a>
      </div>
    );
  }

  return (
    <div className="doc-preview">
      <div className="doc-preview-mark" aria-hidden="true">
        {extension}
      </div>
      <div className="doc-preview-meta">
        <strong>{artifact.filename}</strong>
        <span>
          {formatBytes(artifact.size_bytes)} · created {formatDate(artifact.created_at)}
        </span>
      </div>
      <p className="doc-preview-note">
        This {extension} deliverable was written by the local agent. The API does not expose a text
        extract for binary Office files, so download it to open it in Word, Excel or PowerPoint.
      </p>
      <a
        className="button button-primary button-small"
        href={artifactDownloadUrl(artifact.id)}
        download={artifact.filename}
      >
        <span>↓</span> Download {extension}
      </a>
    </div>
  );
}
