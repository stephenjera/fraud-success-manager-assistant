# Fraud Insight & Rule Copilot

An AI copilot for fraud analysts: natural-language exploration of transaction
data, pattern validation, and rule drafting — ending in a backtested, fully
provenanced SQL `WHERE` clause rule ready for a downstream rule engine.

**Status:** P0–P5 done (incl. P2.5, P3.5). `make lint` / `make test` /
`make eval` all green.
The spec is the source of truth: [`docs/system-spec.md`](./docs/system-spec.md).

The decision record lives in [`docs/decisions/`](./docs/decisions/)
(ADR-0001 through ADR-0016). The detailed design docs live in
[`docs/architecture/`](./docs/architecture/). The UX frames live in
[`docs/ux/wireframes.html`](./docs/ux/wireframes.html).

## What's built

| Phase | What shipped | Status |
|-------|-------------|--------|
| P0 | Spec, ADRs, architecture docs, API contract freeze | ✅ done |
| P1 | LangGraph agent, NL→SQL, SSE streaming, core gates, wall test | ✅ done |
| P2 | Rule lifecycle (draft→backtest→approve→deploy), state machine, mock engine | ✅ done |
| P2.5 | Live-mode proof (real Ollama + real reference), bug fixes | ✅ done |
| P3 | Three-pane frontend, chat/workspace/insights/catalog, wireframes | ✅ done |
| P3.5 | Docker Compose at root, Dockerfiles, Playwright STREAM_LOST regression, pg_catalog test | ✅ done |
| P4 | Makefile, mypy in lint, eval harness, docs reconciliation | ✅ done |
| P5 | Conversational rule proposals, run-terminal robustness, prompt supervisor | ✅ done |

## Repository layout

```
backend/    FastAPI + LangGraph backend (Python 3.12, uv)
  app/      Application package (common, agents, api, services, core)
  tests/    pytest suite (wall, validator, flags, backtest math, rule state, rule engine, API, events)
  eval/     Eval harness + golden fixtures
  scripts/  e2e_walktalk.py, seed_reference.py, agent_repl.py, ask.py
  db-init/  Idempotent Postgres init (roles, schemas)
frontend/   React + TypeScript + Tailwind v4 + shadcn/ui (Vite)
  e2e/      Playwright regression tests
docs/       Spec, ADRs, architecture, phases, UX wireframes
```

## Quickstart

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python 3.12 is pinned in `backend/.python-version`)
- Node.js 20+
- Docker (for Postgres + pgadmin)
- An LLM reachable per `.env` (Ollama is the default provider)

### Option 1: Docker Compose (full stack)

```bash
docker compose up -d
```

This starts Postgres, pgadmin, the API (with alembic + seed), and the frontend.

- Frontend: `http://127.0.0.1:5173`
- API health: `http://127.0.0.1:8000/docs`
- Pgadmin: `http://127.0.0.1:5050`

### Option 2: Local dev

```bash
# Start Postgres
docker compose up -d db

# Backend (from backend/)
cd backend
uv sync
make migrate    # alembic upgrade head
make seed       # scripts/seed_reference.py
make api        # uvicorn app.main:app --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Configuration

All configuration is environment-driven via `pydantic-settings` (see
`backend/app/common/settings.py`):

| Variable | Purpose |
|---|---|
| `PG_DSN` / `REFERENCE_DSN` / `APPSTATE_DSN` | Postgres connections (one cluster, two roles) |
| `LLM_PROVIDER` / `LLM_MODEL` | Provider (ollama, openai, anthropic) and model name |
| `LLM_API_BASE` / `LLM_API_KEY` | Endpoint + key for hosted/local provider |
| `ORIGINS` | CORS-allowed frontend origins (JSON list or comma-separated) |
| `LANGFUSE_*` | Self-hosted Langfuse tracing (optional — degrades to no-op) |

## Running checks

```bash
cd backend
make lint    # ruff check + format --check + mypy
make test    # pytest suite
make eval    # deterministic eval subset (validator, flags, backtest math, rule state, rule engine, wall)
```

## Deferred items

Per spec §15, these are intentionally not built yet: the LLM-judged eval
suite (NL→SQL accuracy, faithfulness, safety/redteam — deferred until a
judge model is available), auth/RBAC, real rule-engine integration,
post-deployment drift monitoring, feedback-loop learning.
CI pipeline is out of scope until a real deployment target exists (ADR-0012).
