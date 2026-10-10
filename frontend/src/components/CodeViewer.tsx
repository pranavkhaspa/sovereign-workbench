import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { Artifact } from "../api/types";
import { CopyButton, Spinner } from "./ui";

export interface CodeViewerProps {
  artifact: Artifact;
}

export function CodeViewer({ artifact }: CodeViewerProps): JSX.Element {
  const [state, setState] = useState<{ loading: boolean; error: string | null; text: string }>({
    loading: true,
    error: null,
    text: "",
  });

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, error: null, text: "" });
    api
      .artifactText(artifact.id)
      .then((text) => {
        if (!cancelled) setState({ loading: false, error: null, text });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setState({
          loading: false,
          error: error instanceof Error ? error.message : "Could not read this artifact.",
          text: "",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [artifact.id]);

  if (state.loading) return <Spinner label="Reading artifact locally..." />;
  if (state.error)
    return <p className="panel-message panel-message-error">Preview failed: {state.error}</p>;

  return (
    <div className="code-viewer">
      <div className="code-viewer-bar">
        <span className="mono muted-text">{state.text.split("\n").length} lines</span>
        <CopyButton value={state.text} label="Copy source" />
      </div>
      <pre className="code-preview">
        <code>{state.text}</code>
      </pre>
    </div>
  );
}
