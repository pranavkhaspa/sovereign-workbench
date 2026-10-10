import { useState } from "react";

import type { Citation } from "../api/types";
import { CopyButton, Dialog } from "./ui";

export interface CitationChipsProps {
  citations: Citation[];
}

function chipKey(citation: Citation): string {
  return `${citation.document_id}:${citation.page ?? "-"}:${citation.span ?? "-"}`;
}

export function CitationChips({ citations }: CitationChipsProps): JSX.Element | null {
  const [active, setActive] = useState<Citation | null>(null);

  if (citations.length === 0) return null;
  const unique: Citation[] = [];
  const seen = new Set<string>();
  for (const citation of citations) {
    const key = chipKey(citation);
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(citation);
  }

  return (
    <>
      <div className="citation-strip" aria-label="Sources used for this answer">
        <span className="citation-strip-label">SOURCES</span>
        {unique.map((citation, index) => (
          <button
            key={chipKey(citation)}
            type="button"
            className="citation-chip"
            onClick={() => setActive(citation)}
          >
            <b>{index + 1}</b>
            <span title={citation.filename}>{citation.filename}</span>
            {citation.page ? <i>p.{citation.page}</i> : null}
          </button>
        ))}
      </div>
      <Dialog
        open={active !== null}
        onClose={() => setActive(null)}
        title={active?.filename ?? "Source excerpt"}
        description={
          active?.page ? `Retrieved locally · page ${active.page} · score ${active.score}` : undefined
        }
        footer={
          active ? <CopyButton value={active.span ?? active.filename} label="Copy excerpt" /> : null
        }
      >
        {active?.span ? (
          <p className="citation-snippet">{active.span}</p>
        ) : (
          <p className="citation-snippet citation-snippet-muted">
            No stored excerpt for this reference. Open the document in the Knowledge base tab to
            read it in full.
          </p>
        )}
      </Dialog>
    </>
  );
}
