# Models & hardware tiers

The whole point of the model layer is: **same code, different machine, different
models — chosen automatically.** Add a model by adding a row to `models/models.toml`.

## Tiers

| Tier | Target machine | Typical models |
| --- | --- | --- |
| `min` | i3 3rd gen · 8 GB RAM · 2 GB GPU | 1B–3B quantized (Q4_K_M) |
| `standard` | 16 GB RAM · 8 GB GPU | 7B quantized |
| `large` | 32 GB+ RAM · 16 GB+ GPU | 14B–32B quantized |
| `remote` | optional cloud API (off in air-gap) | hosted models |

`HARDWARE_TIER` in `.env` selects the ceiling. The router never picks a model above the
configured tier.

## Capabilities

`chat` · `plan` (instruction-following for the planner) · `code` · `vision` · `embed`.

The router classifies each task and picks the best *available* model that declares the
needed capability within the tier. Example: a code request → `code` model; “read this
scanned drawing” → `vision` + OCR; “summarise this memo” → `chat` model.

## Minimum-tier picks (8 GB / 2 GB GPU)

| Role | Model | Why |
| --- | --- | --- |
| Plan / chat | `qwen2.5:3b-instruct-q4_K_M` | strong instruction following at ~2 GB |
| Code | `qwen2.5-coder:3b-instruct-q4_K_M` | best small coder |
| Utility | `qwen2.5:1.5b-instruct-q4_K_M` | fast fallbacks, classification |
| Vision | `moondream2` (Q4) or `smolvlm:500m` | scanned docs/drawings on small GPUs |
| Embeddings | `bge-small-en-v1.5` (CPU) | tiny, good, runs without GPU |
| OCR | Tesseract (`pytesseract`) | CPU, no model download |

> On a 2 GB GPU, keep only **one** model loaded at a time. Ollama unloads idle models;
> set `OLLAMA_MAX_LOADED_MODELS=1` and `OLLAMA_NUM_PARALLEL=1`.

## Larger-tier picks

`qwen2.5:14b`/`32b`, `qwen2.5-coder:14b`/`32b`, `qwen2-vl:7b` for vision,
`bge-large` / `nomic-embed-text` for embeddings.

## Remote (fallback, air-gap-disabled)

Any OpenAI-compatible endpoint: OpenAI, OpenRouter, vLLM on a big server. Enabled only
when `AIRGAP=false` **and** the relevant key is set.

## Rules

1. New model = one row in `models/models.toml` (+ `scripts/pull-models.sh` if local).
2. Never hardcode a model id in feature code — ask the router.
3. Prefer the smallest model that meets the capability; the min tier must always work.
4. Record the chosen model in the audit log for every task (reproducibility).

## Setup commands

The root-level pull script reads the registry rather than maintaining a second list of
model names:

```bash
./scripts/pull-models.sh --dry-run  # inspect the default min-tier selection
./scripts/pull-models.sh             # pull local Ollama rows in the min tier
./scripts/pull-models.sh --all-local
./scripts/pull-models.sh --model planner-min
```

It ignores `provider=local` embeddings and all `remote=true` rows because those are not
Ollama weights. The default min-tier embedding implementation is the dependency-free
hashing embedder; `sentence-transformers` is optional and should be provisioned
separately when the machine has the required cached packages and model files. Complete
model pulls before disconnecting the host. In Compose, set `OLLAMA_USE_COMPOSE=1` so the
weights are placed in the `ollama-models` volume used by the deployment.
Ollama publishes the minimum-tier vision model under `moondream`; the script creates
the `moondream2` alias required by the current registry after pulling it.

The registry's [`qwen2.5:3b-instruct-q4_K_M`](https://ollama.com/library/qwen2.5:3b-instruct-q4_K_M)
and [`qwen2.5-coder:3b-instruct-q4_K_M`](https://ollama.com/library/qwen2.5-coder:3b-instruct-q4_K_M)
currently have the Qwen Research License, not a
permissive licence. They need replacing in `models/models.toml` before the project can
claim all minimum-tier model weights satisfy the licence constraint in `CONTEXT.md`.
Likewise, confirm large-tier Ollama names with the model publisher before invoking
`--all-local`; the current `qwen2-vl:7b` row is not published under that library name.
