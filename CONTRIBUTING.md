# Contributing to Sovereign Workbench

Thanks for helping. This project is built by a two-person team under a hard deadline,
so **clarity and small, reviewable PRs matter more than cleverness.**

## Before you start

1. Read [`CONTEXT.md`](CONTEXT.md) — what we build, for whom, and the rules.
2. Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and, if you touch the model
   layer, [`docs/MODELS.md`](docs/MODELS.md).
3. Pick an unchecked item from [`CHECKLIST.md`](CHECKLIST.md). Frontend items are
   owned by Rohit.

## Workflow

```bash
git checkout -b feat/<scope>-<short>       # or fix/<scope>-<short>
# ... work in small commits ...
make lint && make test
git push -u origin HEAD
gh pr create --fill                        # uses the PR template
```

- One reviewer approval + green CI before merge. **Squash merge.**
- Keep PRs scoped to one checklist item where possible.
- Leave the branch up until reviewed; don’t force-push after review starts.

## Commit messages — Conventional Commits

```
feat(agent): add spreadsheet tool
fix(router): pick vision model for image tasks
docs(context): clarify air-gap rules
chore(ci): cache pip wheels
test(sandbox): assert network is denied
```

## Code standards

### Backend (Python)
- `ruff` + `black` (line length 100) + `mypy` (strict on `core/`).
- Type all public functions. No bare `except`. No global mutable state.
- **Never call a model directly** — always go through `core/llm/router.py`.
- Heavy optional deps (`torch`, `chromadb`, `paddleocr`) must be **lazily imported**.
- Every tool declares a JSON schema and is registered in the tool registry.

### Frontend (TypeScript)
- TypeScript strict, no `any` (use `unknown` + narrow).
- Functional components, hooks, TanStack Query for server state, Zustand for UI state.
- `eslint` + `prettier`; `npm run build` must stay under 500 KB gzip.
- All API shapes come from `src/types/api.ts`; never invent a type inline.

### Security
- **Never commit secrets.** Use `.env` (git-ignored). If you leak one, rotate it and
  say so in the PR.
- Air-gap must **fail closed**: an unexpected egress is blocked and logged.
- Sandboxed code must run with no network and resource limits.

## Branch protection (set by an admin on GitHub)

- Require PR + 1 approval.
- Require `backend-ci`, `frontend-ci` to pass.
- Require branches to be up to date before merge.
- Dismiss stale approvals on new commits.

## Reporting problems

- Bugs / features: use the issue templates.
- Security issues: **do not** open a public issue — see [`SECURITY.md`](SECURITY.md).
