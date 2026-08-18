# Fraud Insight & Rule Copilot

An AI copilot for fraud analysts: natural-language exploration of transaction
data, pattern validation, and rule drafting — ending in a backtested, fully
provenanced SQL `WHERE` clause rule ready for a downstream rule engine.

**Status:** V5 baseline. The repo contains the specification, the
infrastructure skeleton (config, model loading, logging, observability,
health endpoints, frontend scaffold), and the dev dataset. The feature work
described by the spec (agents, API surface, rule lifecycle, eval suite) has
not been started yet. The spec is the source of truth for what comes next:
[`fraud-insight-copilot-spec.md`](./fraud-insight-copilot-spec.md).

## Repository layout

```
backend/    FastAPI + LangGraph backend (Python 3.12, uv)
  app/      Application package (common/ infra; agents, services, … follow)
  data/     Dev dataset (SQLite) + reference schema DDL
frontend/   React + TypeScript + Tailwind v4 + shadcn/ui (Vite)
```

## Quickstart

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python 3.12 is pinned in `backend/.python-version`)
- Node.js 20+
- An LLM reachable per `backend/.env` (Ollama is the default provider)

### Backend

```bash
cd backend
cp .env.example .env   # then fill in LLM_* / Langfuse values
uv sync
uv run python -m uvicorn app.main:app --reload --port 8000
```

- Health: `http://127.0.0.1:8000/api/health` (liveness),
  `/api/health/ready` (LLM + Langfuse configuration state)
- OpenAPI docs: `http://127.0.0.1:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev   # Vite dev server; /api is proxied to http://127.0.0.1:8000
```

## Configuration

All configuration is environment-driven via `pydantic-settings` (see
`backend/app/common/settings.py` and `backend/.env.example`):

| Variable | Purpose |
|---|---|
| `DB_PATH` | Path to the transaction SQLite database |
| `LLM_PROVIDER` / `LLM_MODEL` | Provider (e.g. `ollama`, `openai`, `anthropic`) and bare model name |
| `LLM_API_BASE` / `LLM_API_KEY` | Endpoint + key for hosted/local provider |
| `ORIGINS` | CORS-allowed frontend origins (JSON list or comma-separated) |
| `LANGFUSE_*` | Self-hosted Langfuse tracing (optional — degrades to no-op) |

## Deferred items

Per spec §13, these are intentionally not built yet: auth/RBAC, real rule
engine integration, post-deployment drift monitoring, feedback-loop
learning. The v1 build also does not yet include the agent graph, rule
lifecycle API, eval suite, CI pipeline, or full Docker Compose deployment —
those are the next phases of implementation against the spec.
