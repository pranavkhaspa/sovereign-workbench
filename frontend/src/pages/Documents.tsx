import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, uploadDocument } from "../api/client";
import type { Chunk, Document } from "../api/types";
import { formatBytes, formatDate } from "../lib/format";

const ACCEPTED = ".pdf,.png,.jpg,.jpeg,.xlsx,.xlsm,.docx,.txt,.md,.csv,.log,.json";

function queryError(error: unknown): string | null {
  return error instanceof Error ? error.message : error ? "Request failed" : null;
}

function DocumentIcon({ filename }: { filename: string }): JSX.Element {
  const extension = filename.split(".").pop()?.toUpperCase() ?? "FILE";
  return <span className="document-icon">{extension.slice(0, 4)}</span>;
}

export function DocumentsPage(): JSX.Element {
  const queryClient = useQueryClient();
  const documents = useQuery<Document[]>({ queryKey: ["documents"], queryFn: api.documents });
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({ completed: 0, total: 0 });
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [query, setQuery] = useState("");
  const search = useMutation<Chunk[], Error, string>({
    mutationFn: (value) => api.documentSearch(value, 8),
  });

  const handleFiles = async (fileList: FileList | File[]) => {
    const files = Array.from(fileList);
    if (!files.length) return;
    setUploading(true);
    setUploadError(null);
    setUploadProgress({ completed: 0, total: files.length });
    try {
      for (const file of files) {
        await uploadDocument(file);
        setUploadProgress((current) => ({ ...current, completed: current.completed + 1 }));
      }
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Document indexing failed.");
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
    } finally {
      setUploading(false);
    }
  };

  const submitSearch = () => {
    if (query.trim()) search.mutate(query.trim());
  };

  const documentError = queryError(documents.error);

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <div className="section-kicker">KNOWLEDGE BASE / LOCAL INDEX</div>
          <h1>Documents</h1>
          <p>Index confidential source material for grounded agent runs.</p>
        </div>
        <div className="page-heading-meta">
          <span className="metric-label">INDEXED SOURCES</span>
          <strong>{documents.data?.length ?? "—"}</strong>
          <span>vector retrieval ready</span>
        </div>
      </div>

      <section
        className={`upload-zone panel-grid-lines ${dragging ? "upload-zone-active" : ""}`}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (event.currentTarget === event.target) setDragging(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          void handleFiles(event.dataTransfer.files);
        }}
      >
        <div className="upload-zone-icon">↑</div>
        <div className="upload-zone-copy">
          <h2>
            {uploading
              ? `Indexing ${uploadProgress.completed}/${uploadProgress.total}`
              : "Bring local evidence into the index"}
          </h2>
          <p>
            Drop one or more files or choose from the local filesystem. Nothing is sent off-machine.
          </p>
          <span>PDF · PNG / JPG · DOCX · XLSX · TXT · MD · CSV</span>
        </div>
        <label className="button button-primary">
          {uploading ? (
            <>
              <span className="button-spinner button-spinner-dark" /> Indexing...
            </>
          ) : (
            <>
              Choose files <span>→</span>
            </>
          )}
          <input
            type="file"
            accept={ACCEPTED}
            multiple
            className="visually-hidden"
            onChange={(event) => {
              if (event.target.files) void handleFiles(event.target.files);
              event.target.value = "";
            }}
            disabled={uploading}
          />
        </label>
      </section>
      {uploadError && (
        <div className="panel-message panel-message-error">
          <span>!</span>
          {uploadError}
        </div>
      )}
      {documentError && (
        <div className="panel-message panel-message-error">
          <span>!</span>Could not load documents: {documentError}
        </div>
      )}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <div className="section-kicker">RETRIEVAL / CITED SEARCH</div>
            <h2>Search the local index</h2>
          </div>
          <span className="muted-text">top 8 ranked chunks</span>
        </div>
        <div className="search-row">
          <div className="search-input-wrap">
            <span>⌕</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") submitSearch();
              }}
              placeholder="Search inspection findings, SOP clauses, equipment IDs..."
              aria-label="Search indexed documents"
            />
            <button
              type="button"
              onClick={() => {
                setQuery("");
                search.reset();
              }}
              disabled={!query}
            >
              Clear
            </button>
          </div>
          <button
            className="button button-secondary"
            type="button"
            onClick={submitSearch}
            disabled={!query.trim() || search.isPending}
          >
            {search.isPending ? (
              <>
                <span className="button-spinner" /> Searching
              </>
            ) : (
              <>
                Search <span>→</span>
              </>
            )}
          </button>
        </div>
        {search.error && (
          <div className="panel-message panel-message-error">
            <span>!</span>
            {search.error.message}
          </div>
        )}
        {search.data && search.data.length === 0 && (
          <div className="empty-state compact-empty">
            <span className="empty-mark">⌕</span>
            <strong>No matching excerpts</strong>
            <span>Try a broader phrase or index another source document.</span>
          </div>
        )}
        {search.data && search.data.length > 0 && (
          <div className="search-results">
            {search.data.map((chunk) => (
              <article className="search-result" key={chunk.id}>
                <div className="search-result-meta">
                  <strong>{chunk.citation.filename}</strong>
                  <span>
                    {chunk.citation.page
                      ? `page ${chunk.citation.page}`
                      : (chunk.citation.span ?? "local span")}
                  </span>
                  <span className="score-chip">
                    {Math.round(chunk.citation.score * 100)}% match
                  </span>
                </div>
                <p>{chunk.text}</p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="panel document-table-panel">
        <div className="panel-heading">
          <div>
            <div className="section-kicker">INDEX INVENTORY</div>
            <h2>Source documents</h2>
          </div>
          <span className="muted-text">{documents.data?.length ?? 0} records</span>
        </div>
        {documents.isPending ? (
          <div className="loading-row">
            <span className="button-spinner" /> Loading index...
          </div>
        ) : documents.data?.length ? (
          <div className="document-table-wrap">
            <table className="document-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Format</th>
                  <th>Chunks</th>
                  <th>Size</th>
                  <th>Indexed</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {documents.data.map((document) => (
                  <tr key={document.id}>
                    <td>
                      <div className="document-name">
                        <DocumentIcon filename={document.filename} />
                        <strong title={document.filename}>{document.filename}</strong>
                      </div>
                    </td>
                    <td className="muted-text">{document.content_type.split("/").pop()}</td>
                    <td className="mono">{document.chunk_count}</td>
                    <td className="muted-text">{formatBytes(document.size_bytes)}</td>
                    <td className="muted-text">{formatDate(document.created_at)}</td>
                    <td>
                      <span className={`status-tag status-tag-${document.status.toLowerCase()}`}>
                        {document.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <span className="empty-mark">▤</span>
            <strong>Your local index is empty</strong>
            <span>
              Upload a PDF, report, spreadsheet, or image above to make it available to the agent.
            </span>
          </div>
        )}
      </section>
    </div>
  );
}
