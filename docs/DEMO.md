# Frontend demo — 2-minute script and screenshot shots

Two things live here: the spoken **2-minute script** (SIH jury timing) and the
**shot list** for the three screenshots that go in `docs/assets/` and the idea PPT.
Everything can be produced from the frontend alone using mock mode; the live
backend path is listed as a substitute where it matters.

---

## 0. Running it

```bash
cd frontend
npm install

# Mock mode — no backend, no model weights, every §4 route answered in-browser
# by frontend/scripts/seed.ts. Use this for screenshots and rehearsals.
echo "VITE_USE_MOCK=true" > .env.local
npm run dev          # http://127.0.0.1:5173

# Live mode — proxy /api to the backend (./scripts/dev.sh runs both)
rm .env.local
npm run dev
```

Rehearse at **1280 × 720**, dark theme, browser chrome hidden.

---

## 1. The 2-minute script (120 s)

| # | Segment | Seconds | What the speaker says / does |
| --- | --- | --- | --- |
| 1 | **Problem** | 0:00 – 0:15 | Refinery and PSU work is confidential, so it cannot go to ChatGPT/Claude. Staff either type it manually or leak it into public tools. We built the on-prem equivalent. |
| 2 | **Live run** | 0:15 – 1:15 | Press **Run** on a prompt like *"Read the attached inspection report and draft an approval note as a Word file."* Narrate as it streams: **plan → local tool calls → citations → `.docx` deliverable**. Point at the timeline (each tool call and its elapsed time), the citation chips, and the sovereignty badge showing **external calls 0**. Download/preview the artifact without leaving the page. |
| 3 | **How built** | 1:15 – 1:45 | React + Vite + TS, streaming over SSE through one typed transport seam; mock and real backends are swappable with `VITE_USE_MOCK`. The model router picks a small open-weight model per task type (reasoner vs coder) and blocks remote providers while air-gapped. |
| 4 | **Next** | 1:45 – 2:00 | Runs on the 8 GB / i3 / 2 GB GPU target, connects into the full workbench (RAG, OCR, sandbox, egress audit), and extends by editing `models/models.toml`. |

Do not open Settings or Documents during the 2 minutes — they are backup shots
only if a judge asks.

---

## 2. Shot list (3 screenshots, 1280 × 720)

Export to `docs/assets/` with these names. All three are reachable in mock mode.

| File | Tab | State to capture | Why this shot |
| --- | --- | --- | --- |
| `01-workbench-run.png` | **Workbench** | Mid-run: answer text streaming, timeline showing `plan` → `tool_call` → `tool_result` with `+elapsed` timings, at least one citation chip visible under the answer. | Proves the agent plans, calls local tools, and grounds its answer. |
| `02-artifact-preview.png` | **Workbench** | Run complete: `Artifacts` list with `Approval-Note-Unit12.docx` and the **Preview** dialog open showing the deliverable. | Proves the output is a real file, not a chat reply. |
| `03-sovereignty.png` | **Sovereignty** | `AIRGAP ON`, **external calls blocked: 0**, the local-endpoint list, and a few audit rows below. | Proves sovereignty — the judged requirement. |

Capture with a clean browser window, no cursor over the primary content, and no
dev-server error overlay. If a shot needs the light theme (README), retake shot 1
with the Settings → appearance toggle switched, saved as `04-workbench-light.png`.

---

## 3. Backups, if time allows

| File | Tab | State |
| --- | --- | --- |
| `05-models.png` | **Models** | Cards for the minimum-tier models with capabilities/tier, one remote provider visibly blocked by air-gap. |
| `06-settings.png` | **Settings** | Config summary, appearance toggle, copy-diagnostics JSON, shortcut list. |

---

## 4. Judged claims and where they show up

| Claim from SIH26117 | Where the judge sees it |
| --- | --- |
| Scanned report → findings → `.docx` | Shot 2 (artifact preview), segment 2 |
| Sandboxed coding task | Timeline showing `code_exec` + `exit 0` (rerun prompt *"write a python script…"*) |
| Multimodal understanding | Documents tab upload of a scanned page + OCR/vision step in the timeline |
| Model auto-selection | Composer model picker grouped by capability; `plan` event shows the chosen `model_id` |
| Proof of sovereignty | Shot 3 + `scripts/verify-airgap.sh` |
| 8 GB / i3 / 2 GB GPU | `docs/MODELS.md` minimum tier, confirmed with `scripts/pull-models.sh` |
