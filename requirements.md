# Fraud Success Manager (FSM) Assistant — Requirements

## Active LLM Model
`ollama:qwen3.6:27b-128k-agent` (as configured in `backend/.env`)

---

## A. NL→SQL Core (MVP Guardrails)

| ID | Requirement | Status |
|----|-------------|--------|
| A-1 | LLM generates syntactically valid SQL that executes against the schema | Partial — validates via `LIMIT 0` |
| A-2 | Read-only enforcement at DB connection level | ✅ Done |
| A-3 | Statement-type validation on `/api/execute` — reject non-SELECT (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, etc.) | ✅ Done |
| A-4 | Row-limit cap on `/api/execute` — append `LIMIT` if absent, reject if result exceeds threshold (default 10,000) | ✅ Done |
| A-5 | Query timeout enforcement on `/api/execute` — DuckDB timeout (default 30s) | ✅ Done |
| A-6 | Ambiguous queries trigger clarification response, not silent guessing — system prompt update | ❌ |
| A-7 | Confidence scoring — LLM outputs a 0-1 confidence on its own SQL | ❌ |
| A-8 | Config alignment — `.env` keys (`DB_PATH`, `LLM_API_BASE`, `ORIGINS`) mapped to `config.py` `Settings` model | ✅ Done |
| A-9 | CORS restricted to configured origins only (not wildcard `*`) | ✅ Done |

## B. Insight-to-Rule Workflow

| ID | Requirement | Status |
|----|-------------|--------|
| B-1 | Rule predicate generation from exploration results | ✅ Done |
| B-2 | Rule backtesting with confusion matrix (TP/FP/FN/TN) | ✅ Done |
| B-3 | Financial metrics configurable via env — `FRAUD_COST`, `FP_COST` (currently hardcoded $500/$50) | ✅ Done |
| B-4 | Human-in-the-loop confirmation in frontend — FSM must explicitly approve SQL/rule before execution | ❌ |
| B-5 | Statistical significance flagging — Fisher's exact test on confusion matrix to detect overfitting | ❌ |

## C. Observability & Logging

| ID | Requirement | Status |
|----|-------------|--------|
| C-1 | Langfuse integration — trace ID on every LLM call, captures prompt, response, tokens, latency | ✅ Done (verified in UI: 7 traces) |
| C-2 | Token usage tracking per session (cumulative cost proxy) | ✅ Done |
| C-3 | Prompt version tracking in Langfuse spans (`PROMPT_VERSION` from `builder.py`) | ✅ Done |
| C-4 | Query execution audit trail — each `/execute` and `/explore` call logged with session ID, timestamp, SQL, latency | ✅ Done |

## D. Evaluation Framework

| ID | Requirement | Status |
|----|-------------|--------|
| D-1 | Hand-written NL→SQL test set — 20 pairs: ~10 simple, ~5 moderate, ~5 edge cases | ✅ Done |
| D-2 | Execution accuracy scorer — generated SQL runs successfully and returns non-empty results | ✅ Done |
| D-3 | Query validity rate — % of generated SQL that passes syntax/schema validation | ✅ Done |
| D-4 | Latency metric — p50/p95 per request type | ✅ Done |
| D-5 | Rule precision/recall scorer — evaluate generated predicates against `fraud_labels` | ✅ Done |
| D-6 | Eval script — single command (`python -m tests.evaluate`) that runs all tests and prints summary | ✅ Done |
| D-7 | Unit tests for safety guardrails — statement validation, LIMIT enforcement, timeout | ✅ Done (41 tests) |

## E. Session & History

| ID | Requirement | Status |
|----|-------------|--------|
| E-1 | Session persistence via SQLite — survive backend restart | ❌ |
| E-2 | Session TTL — auto-expire sessions older than configurable age (default 24h) | ❌ |
| E-3 | Load past session from frontend — dropdown or session ID input | ❌ |

## F. Documentation

| ID | Requirement | Status |
|----|-------------|--------|
| F-1 | Root `README.md` — setup instructions, architecture rationale, evaluation guide, known limitations | ✅ |
| F-2 | Productionization design note — monitoring, access control, rate limiting, rule review workflow | ✅ |

## G. Code Quality

| ID | Requirement | Status |
|----|-------------|--------|
| G-1 | Dead code removal — `session_hooks.py`; unused imports | ✅ Done |
| G-2 | Remove unused frontend dependencies — `@codemirror/lang-sql`, `@uiw/react-codemirror`, `@tanstack/react-query`, `@tanstack/react-router`, `axios`, `lucide-react`; delete `api/client.ts` | ✅ Done |
| G-3 | Type coverage on critical paths — ANN rules pass; fixed I001/F401/UP017 | ✅ Done |
| G-4 | No hardcoded secrets — `.env` properly excluded | ✅ Done |

---

## Implementation Order

1. **Phase 1**: A-3, A-4, A-5, A-8, A-9 (Safety + Config)
2. **Phase 2**: C-1, C-2, C-3, C-4 (Langfuse + Observability)
3. **Phase 3**: D-1, D-2, D-3, D-4, D-5, D-6, D-7 (Evaluation Framework)
4. **Phase 4**: A-6, A-7, B-3, B-4, B-5 (NL→SQL Hardening + Rule Improvements)
5. **Phase 5**: E-1, E-2, E-3 (Session Persistence)
6. **Phase 6**: F-1, F-2, G-1, G-2, G-3 (Documentation + Quality)
7. **Phase 7**: Frontend cleanup (dead deps, UI polish, human-in-the-loop UX)
