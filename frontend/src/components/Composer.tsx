import { useRef, useState } from "react";

import { uploadDocument } from "../api/client";
import type { Document, ModelInfo, TaskOptions } from "../api/types";
import { formatBytes } from "../lib/format";
import { useSession } from "../store/useSession";

interface Props {
  models: ModelInfo[];
  documents: Document[];
  running: boolean;
  disabled?: boolean;
  onDocumentsUploaded?: () => void;
  onStop?: () => void;
  onSubmit: (
    prompt: string,
    modelId: string | null,
    options: TaskOptions,
    attachments: string[],
  ) => void;
}

const ALLOWED_FILES = ".pdf,.png,.jpg,.jpeg,.xlsx,.xlsm,.docx,.txt,.md,.csv";

export function Composer({
  models,
  documents,
  running,
  disabled = false,
  onDocumentsUploaded,
  onStop,
  onSubmit,
}: Props): JSX.Element {
  const [prompt, setPrompt] = useState(
    "Read the attached inspection report and draft an approval note as a Word file.",
  );
  const [writeFiles, setWriteFiles] = useState(true);
  const [runCode, setRunCode] = useState(false);
  const [maxSteps, setMaxSteps] = useState("8");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [documentToAdd, setDocumentToAdd] = useState("");
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const {
    selectedModelId,
    attachments,
    airgap,
    setSelectedModelId,
    addAttachment,
    removeAttachment,
  } = useSession();

  const resizePrompt = (value: string) => {
    setPrompt(value);
    const element = textAreaRef.current;
    if (element) {
      element.style.height = "auto";
      element.style.height = `${Math.min(element.scrollHeight, 220)}px`;
    }
  };

  const handleFiles = async (fileList: FileList | File[]) => {
    const files = Array.from(fileList);
    if (files.length === 0) return;
    setUploading(true);
    setUploadError(null);
    try {
      for (const file of files) {
        const result = await uploadDocument(file);
        addAttachment({
          id: result.document_id,
          filename: file.name,
          sizeBytes: file.size,
          contentType: file.type || "application/octet-stream",
        });
      }
      onDocumentsUploaded?.();
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Attachment upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const addExistingDocument = () => {
    const document = documents.find((item) => item.id === documentToAdd);
    if (document) {
      addAttachment({
        id: document.id,
        filename: document.filename,
        sizeBytes: document.size_bytes,
        contentType: document.content_type,
      });
    }
    setDocumentToAdd("");
  };

  const submit = () => {
    if (!prompt.trim() || running || disabled) return;
    const parsedMaxSteps = Number.parseInt(maxSteps, 10);
    onSubmit(
      prompt.trim(),
      selectedModelId,
      {
        allow_network: false,
        write_files: writeFiles,
        run_code: runCode,
        max_steps: Number.isFinite(parsedMaxSteps) && parsedMaxSteps > 0 ? parsedMaxSteps : null,
      },
      attachments.map((attachment) => attachment.id),
    );
  };

  return (
    <section className="composer-panel panel-grid-lines">
      <div className="section-kicker">TASK CONSOLE / LOCAL EXECUTION</div>
      <div className="composer-heading">
        <div>
          <h2>What should the workbench execute?</h2>
          <p>Describe the deliverable, constraints, and evidence you need from local sources.</p>
        </div>
        <span className={`secure-chip ${airgap ? "" : "secure-chip-warning"}`}>
          <span className="status-dot" /> {airgap ? "air-gap enforced" : "network policy active"}
        </span>
      </div>

      <textarea
        ref={textAreaRef}
        className="prompt-input"
        value={prompt}
        rows={3}
        onChange={(event) => resizePrompt(event.target.value)}
        onKeyDown={(event) => {
          if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
            event.preventDefault();
            if (running) onStop?.();
            else submit();
          }
        }}
        placeholder="Example: compare the inspection findings with the maintenance SOP and draft an approval note..."
        aria-label="Task prompt"
        disabled={disabled}
      />

      <div
        className={`attachment-dropzone ${dragging ? "attachment-dropzone-active" : ""}`}
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
        <div className="attachment-drop-copy">
          <span className="drop-icon">↓</span>
          <div>
            <strong>
              {uploading ? "Indexing attachment locally..." : "Drop evidence files here"}
            </strong>
            <span>PDF, image, Word, Excel, text · files stay on this machine</span>
          </div>
        </div>
        <label className="button button-secondary button-small upload-button">
          <span>+</span> Add files
          <input
            type="file"
            accept={ALLOWED_FILES}
            multiple
            className="visually-hidden"
            onChange={(event) => {
              if (event.target.files) void handleFiles(event.target.files);
              event.target.value = "";
            }}
            disabled={uploading || disabled}
          />
        </label>
      </div>

      <div className="attachment-list" aria-live="polite">
        {attachments.map((attachment) => (
          <div className="attachment-pill" key={attachment.id}>
            <span className="file-badge">
              {attachment.filename.split(".").pop()?.toUpperCase() ?? "FILE"}
            </span>
            <span className="attachment-name" title={attachment.filename}>
              {attachment.filename}
            </span>
            <span className="muted-text">{formatBytes(attachment.sizeBytes)}</span>
            <button
              className="icon-button"
              type="button"
              onClick={() => removeAttachment(attachment.id)}
              aria-label={`Remove ${attachment.filename}`}
            >
              ×
            </button>
          </div>
        ))}
        {attachments.length === 0 && (
          <span className="muted-text">No evidence attached to this run.</span>
        )}
      </div>

      <div className="composer-controls">
        <label className="field-label" htmlFor="model-select">
          MODEL ROUTE
          <select
            id="model-select"
            className="select-control"
            value={selectedModelId ?? ""}
            onChange={(event) => setSelectedModelId(event.target.value || null)}
            disabled={disabled}
          >
            <option value="">AUTO · ROUTER DECIDES</option>
            {models.map((model) => (
              <option key={model.id} value={model.id} disabled={!model.available || model.remote}>
                {model.label} · {model.available ? model.tier.toUpperCase() : "OFFLINE"}
              </option>
            ))}
          </select>
        </label>
        <label className="field-label" htmlFor="document-select">
          ADD INDEXED SOURCE
          <span className="inline-select-row">
            <select
              id="document-select"
              className="select-control"
              value={documentToAdd}
              onChange={(event) => setDocumentToAdd(event.target.value)}
              disabled={disabled || documents.length === 0}
            >
              <option value="">Choose document...</option>
              {documents.map((document) => (
                <option key={document.id} value={document.id}>
                  {document.filename}
                </option>
              ))}
            </select>
            <button
              className="button button-secondary button-small"
              type="button"
              onClick={addExistingDocument}
              disabled={!documentToAdd}
            >
              Add
            </button>
          </span>
        </label>
        <label className="field-label narrow-field" htmlFor="max-steps">
          MAX STEPS
          <input
            id="max-steps"
            className="text-control"
            value={maxSteps}
            onChange={(event) => setMaxSteps(event.target.value)}
            inputMode="numeric"
            disabled={disabled}
          />
        </label>
      </div>

      <div className="composer-footer">
        <div className="toggle-group">
          <label className="toggle-control">
            <input
              type="checkbox"
              checked={writeFiles}
              onChange={(event) => setWriteFiles(event.target.checked)}
              disabled={disabled}
            />
            <span /> write artifacts
          </label>
          <label className="toggle-control">
            <input
              type="checkbox"
              checked={runCode}
              onChange={(event) => setRunCode(event.target.checked)}
              disabled={disabled}
            />
            <span /> sandbox code
          </label>
          <span className="muted-text">Ctrl / ⌘ + Enter to run</span>
        </div>
        {running ? (
          <button className="button button-danger run-button" type="button" onClick={onStop}>
            <span className="stop-glyph" aria-hidden="true" /> Stop run
          </button>
        ) : (
          <button
            className="button button-primary run-button"
            type="button"
            onClick={submit}
            disabled={disabled || !prompt.trim() || uploading}
          >
            Run task <span>→</span>
          </button>
        )}
      </div>
      {uploadError && <p className="inline-error">{uploadError}</p>}
    </section>
  );
}
