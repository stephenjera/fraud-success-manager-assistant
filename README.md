# Fraud Success Manager (FSM) Assistant

A production-grade, GenAI-powered assistant that helps Fraud Success Managers explore transaction data, discover fraud patterns, and translate insights into deployable fraud rules.

## Overview

The FSM Assistant gives fraud analysts a natural-language interface to:

1. **Explore** — ask questions in plain English and receive safe, validated SQL queries against a fraud analytics database.
2. **Validate** — backtest generated rules against historical fraud labels with precision/recall, confusion matrices, and statistical significance tests.
3. **Iterate** — sessions persist via SQLite so multi-turn investigations survive backend restarts.

The system is designed so that every generated SQL query and rule is visible to the analyst before execution — no blind trust in the LLM.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React + Vite)                  │
│  Chat UI  │  DataGrid (query + results)  │  Rule Studio (edit) │
└──────────────────────┬──────────────────────────────────────────┘
                       │  HTTP / JSON
┌──────────────────────▼──────────────────────────────────────────┐
│                     Backend (FastAPI)                            │
│                                                                  │
│  /api/explore   ── NL→SQL agent (pydantic-ai + Ollama LLM)     │
│  /api/execute   ── Safe SQL execution against DuckDB            │
│  /api/rules/*   ── Rule backtesting + confusion matrix          │
│  /api/sessions  ── CRUD for persistent sessions (SQLite)        │
└──────────────────────────┬───────────────────────────────────────┘
                           │
             ┌─────────────┴──────────────┐
             │                           │
       ┌─────▼──────┐            ┌───────▼────────┐
       │  DuckDB    │            │  SQLite        │
       │  (analytics│            │  (sessions     │
       │   DB)      │            │   DB)          │
       └────────────┘            └────────────────┘
```

### Backend Stack

| Component | Library | Purpose |
|-----------|---------|---------|
| Web framework | **FastAPI** | REST API, async support, automatic OpenAPI docs |
| Agent framework | **pydantic-ai** | LLM prompting, tool calling, output validation, retries |
| Database (analytics) | **DuckDB** | In-memory analytical queries over transaction data |
| Database (sessions) | **SQLite** | Persistent chat history + execution logs |
| Observability | **Langfuse** | Trace LLM calls, token usage, latency |
| Config | **pydantic-settings** | Type-safe `.env`-backed configuration |
| Scheduler / runtime | **uvicorn** | ASGI server |

### Frontend Stack

| Component | Library | Purpose |
|-----------|---------|---------|
| UI framework | **React 19** | Component-based chat + data panels |
| Build tool | **Vite 8** | Fast dev server + production builds |
| Styling | **Tailwind CSS 4** | Utility-first, dark theme |
| LLM | **Ollama: `qwen3.6:27b-128k-agent`** | Local LLM for NL→SQL translation |

### Session Persistence

Chat history is stored in SQLite at `backend/app/data/sessions.db`:

- **`sessions`** — metadata (ID, created/updated timestamps)
- **`chat_messages`** — per-message rows serialised via pydantic-ai's `ModelMessagesTypeAdapter` (native JSON, version-resilient)
- **`execution_logs`** — audit trail with SQL, row counts, latency

Sessions auto-expire after a configurable TTL (default 24 h, set via `SESSION_TTL_HOURS` in `.env`).

### Safety Guardrails

| ID | Guardrail | Implementation |
|----|-----------|----------------|
| A-2 | Read-only enforcement | DuckDB connection in read-only mode |
| A-3 | Statement-type validation | Rejects all non-SELECT statements (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE) |
| A-4 | Row-limit cap | Auto-appends `LIMIT 10000` (configurable via `QUERY_MAX_ROWS`) |
| A-5 | Query timeout | 30-second timeout enforced via `anyio.move_on_after` (configurable via `QUERY_TIMEOUT_SECONDS`) |
| A-9 | CORS restriction | Origins must be explicitly listed in `ORIGINS`; wildcard `*` is prohibited |

## Setup

### Prerequisites

- **Python 3.12+** (managed via uv)
- **Node.js 20+** (for frontend)
- **Ollama** running locally with the `qwen3.6:27b-128k-agent` model pulled

### Install

```bash
# 1. Backend dependencies
cd backend
uv sync

# 2. Frontend dependencies
cd ../frontend
npm install
```

### Configuration

Copy and edit the environment file:

```bash
cd backend
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `ollama:qwen3.6:27b-128k-agent` | LLM identifier |
| `LLM_API_BASE` | `http://localhost:11434` | Ollama API endpoint |
| `ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |
| `QUERY_MAX_ROWS` | `10000` | Maximum rows returned by a query |
| `QUERY_TIMEOUT_SECONDS` | `30` | Max query execution time |
| `SESSION_TTL_HOURS` | `24` | Hours before sessions auto-expire |
| `FRAUD_COST` | `500.0` | Imputed cost per missed fraud ($USD) |
| `FP_COST` | `50.0` | Imputed cost per false positive ($USD) |
| `LANGFUSE_*` | — | Optional Langfuse tracing credentials |

## Running

### Development

Open two terminals:

```bash
# Terminal 1 — Backend (port 8000)
cd backend
uv run uvicorn app.main:app --port 8000 --reload

# Terminal 2 — Frontend (port 5173)
cd frontend
npm run dev
```

The frontend proxy forwards `/api/*` requests to the backend at `http://localhost:8000`.

### Frontend Build

```bash
cd frontend
npm run build
```

## Evaluation

### Offline (Guardrail Tests)

Runs 41 unit tests covering statement validation, row-limit enforcement, timeout, CORS, and session persistence. Fast, no LLM required.

```bash
cd backend
uv run pytest tests/test_safety_guardrails.py -v
```

### Online (NL→SQL Pipeline)

End-to-end evaluation against a hand-written test set of NL→SQL pairs. Requires the backend and LLM running.

```bash
cd backend
# --offline  — run guardrail tests only (fast)
uv run python -m tests.evaluate --offline

# --online   — run NL→SQL accuracy + latency tests (needs running backend + LLM)
uv run python -m tests.evaluate --online

# --limit N  — restrict to first N test cases
uv run python -m tests.evaluate --online --limit 5
```

### Test Set

The evaluation suite includes ~20 hand-crafted NL→SQL pairs spanning:
- **Simple** (~10 queries): single-table, basic aggregation
- **Moderate** (~5 queries): multi-table joins, subqueries
- **Edge cases** (~5 queries): ambiguous prompts, rule predicates, clarification triggers

## Known Limitations

| Limitation | Impact | Mitigation / Next Step |
|------------|--------|------------------------|
| No authentication | Anyone with network access can query the API | Add API-key auth or OAuth2/OIDC (see backend/README.md) |
| No rate limiting | Unbounded LLM calls risk cost/abuse | FastAPI middleware with per-user throttling |
| Session cap not enforced | Unbounded session growth in SQLite | Add max-session count or cron cleanup |
| LLM hallucination risk | Columns, tables, or values may be invented | Structured output validation, confidence gating, retry budgets |
| Read-only analytics only | Cannot modify source data | Intentional — write operations blocked at DB + API layers |
| Single-tenant | No multi-user isolation | Add tenant-scoped sessions and query sandboxes |
| Ollama dependency | Requires local LLM runtime | Swap to OpenAI-compatible endpoint via config |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── agent/              # pydantic-ai agent, prompts, tools, validators
│   │   │   ├── copilot.py      # Main agent definition + output validators
│   │   │   ├── prompts/        # Prompt templates + builder
│   │   │   └── types.py        # Agent dependency types
│   │   ├── api/
│   │   │   ├── routers/        # FastAPI route handlers
│   │   │   │   ├── explore.py  # NL→SQL agent orchestration
│   │   │   │   ├── execute.py  # Safe SQL execution
│   │   │   │   ├── rules.py    # Rule backtesting
│   │   │   │   └── sessions.py # Session CRUD endpoints
│   │   │   ├── services/       # Business logic
│   │   │   │   ├── analytics.py      # Rule metrics computation
│   │   │   │   ├── query_safety.py   # Statement validation, LIMIT enforcement
│   │   │   │   ├── session.py        # Session manager (proxies to session_store)
│   │   │   │   └── session_store.py  # SQLite-backed persistence
│   │   │   └── schemas.py      # Pydantic request/response models
│   │   ├── config.py           # pydantic-settings + lifecycle hooks
│   │   ├── database.py         # DuckDB connection management
│   │   ├── logger.py           # Structured logging setup
│   │   ├── main.py             # FastAPI app, startup/shutdown hooks
│   │   └── observability.py    # Langfuse integration
│   ├── data/                   # SQLite sessions database (runtime)
│   ├── tests/                  # Evaluation suite + guardrail tests
│   └── pyproject.toml          # Dependencies + ruff config
├── frontend/
│   └── src/
│       ├── App.tsx             # Main layout, session state, API calls
│       └── components/
│           ├── ChatStream.tsx  # Chat UI with session dropdown
│           ├── DataGrid.tsx    # Query editor + results grid
│           ├── RuleStudio.tsx  # Rule predicate editor + backtest metrics
│           └── ApprovalBanner.tsx  # Human-in-the-loop confirmation
└── requirements.md             # Full requirements traceability matrix
```

## License

Internal use. See your organisation's policy for details.