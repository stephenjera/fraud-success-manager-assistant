# Productionization Design Note

This document outlines how to take the FSM Assistant from a working prototype to a production-ready system in a fraud operations environment.

## 1. Authentication & Authorization

### Current State

The API has no authentication or authorization. Any process with network access to port 8000 can execute queries, run the NL→SQL agent, or delete sessions.

### Recommended Approach

**Internal service-to-service:** API key authentication via FastAPI middleware. Each consuming service gets a rotating key with a scoped token (e.g., `explore-only`, `execute-only`, `admin`).

**User-facing auth:** Integrate with the organisation's SSO — OIDC via Auth0, Okta, or internal identity provider. Frontend obtains a JWT, backend validates it via `httpx` middleware.

**Role-based access:** At minimum, two roles:
- **Analyst** — read-only session access, can generate and test rules, cannot deploy
- **Approver** — can review and approve rules for deployment to the fraud rules engine

### Implementation Path

1. Add `fastapi-users` or `authlib` for JWT/OIDC integration
2. Wrap all routes with `Depends(get_current_user)`
3. Persist user ID in session metadata for audit trail

## 2. Rate Limiting

### Current State

No rate limits. A single user session can trigger unlimited LLM calls, which are expensive and can exhaust Ollama resources.

### Recommended Approach

Use `slowapi` (FastAPI integration of `limits`) with three tiers:

| Endpoint | Limit | Rationale |
|----------|-------|-----------|
| `/api/explore` | 10 req/min per user | LLM calls are expensive; 10/min accommodates interactive iteration |
| `/api/execute` | 60 req/min per user | DuckDB is local but unbounded queries can saturate CPU |
| `/api/rules/evaluate` | 30 req/min per user | Backtesting runs heavy aggregations |

Per-IP throttling as a secondary layer to prevent credential abuse.

### Implementation Path

1. Add `slowapi` to dependencies
2. Create `RateLimitMiddleware` with user-scoped identifiers
3. Return `429 Too Many Requests` with `Retry-After` header

## 3. Monitoring & Alerting

### Current State

Langfuse integration provides LLM trace visibility (prompt, response, tokens, latency). Pydantic-ai OTel instrumentation captures span metrics.

### Recommended Enhancements

**Application metrics (Prometheus):**
- `fsm_query_latency_seconds` — histogram with p50/p95 buckets per endpoint
- `fsm_llm_tokens_total` — cumulative token usage by session
- `fsm_guardrail_rejections_total` — counter of rejected unsafe queries
- `fsm_errors_total` — counter of exceptions by route

**Hallucination signals:**
- Track confidence scores below a threshold (e.g., `confidence_score < 0.7`)
- Alert on `clarification_request` spikes (may indicate model drift)
- Flag when output validator retries exceed 2 (signals schema misalignment)

**Alerting rules (Alertmanager):**
| Alert | Condition | Severity |
|-------|-----------|----------|
| HighErrorRate | `fsm_errors_total > 50 per minute` | Critical |
| QueryTimeoutSpike | p95 latency > 25 s for 5 minutes | Warning |
| TokenBudgetWarning | daily token usage > 80% of budget | Warning |
| GuardrailBreach | rejection rate > 30% | Critical |

### Implementation Path

1. Add `prometheus-client` instrumentation in middleware
2. Export `/metrics` endpoint (scraper-only, no auth)
3. Create Prometheus/Grafana dashboards with above metrics
4. Wire Alertmanager with PagerDuty/OpsGenie integration

## 4. Rule Review Workflow

### Current State

The FSM generates a rule predicate, backtests it, and sees metrics. There is no workflow for promoting a rule from "draft" to "deployed."

### Recommended Workflow

```
Generated Rule (draft)
    │
    ▼
FSM Review — edit predicate, check thresholds
    │
    ▼
Approval Queue — approver reviews against SLA criteria:
    ├── Precision > 60%
    ├── False-positive rate < 5%
    ├── Statistically significant (p < 0.05)
    └── Expected impact reviewed (transactions/day)
    │
    ▼
Canary Deployment — rule runs in shadow mode for 24-48h:
    ├── Logs matched transactions without blocking
    ├── Compares shadow vs. production metrics
    └── Approver confirms delta is within bounds
    │
    ▼
Full Deployment — rule goes live in fraud rules engine
    │
    ▼
Post-deployment Monitoring — 7-day drift detection window
    ├── Precision drift > 10% triggers review
    └── FP complaint rate > 1% triggers rollback
```

### Rule Metadata (Persistent)

Each rule should carry:
- `rule_id` (UUID)
- `created_by` (user ID)
- `created_at` / `approved_at` / `deployed_at`
- `status` (draft → approved → canary → deployed → retired)
- `backtest_metrics` (snapshot of precision, recall, confusion matrix at time of approval)
- `production_metrics_7d` (actual performance post-deployment)
- `version_history` (audit trail of edits)

### Implementation Path

1. Add `rules` table to sessions DB (or separate dedicated DB)
2. Extend `/api/rules/` with `POST /create`, `PATCH /approve`, `GET /status`
3. Build canary evaluator that runs approved rules in shadow mode against live traffic
4. Integrate with existing fraud rules engine API for final deployment step

## 5. Database Migration

### Current State

- **DuckDB** — in-memory analytics DB, recreated on each backend restart
- **SQLite** — local session persistence at `backend/app/data/sessions.db`

### Recommended Approach

**Analytics database — migrate to PostgreSQL:**
- Enables concurrent reads, persistent historical data, row-level security
- DuckDB can still query PostgreSQL as an external table for complex analytics
- Schema migration: use `duckdb.query("COPY ... TO 'postgresql://...')` for initial data port

**Session store — migrate to PostgreSQL:**
- SQLite is single-writer — won't scale across multiple backend replicas
- Same schema, different engine — abstract via SQLModel or Tortoise-ORM
- Add connection pooling via `pgbouncer`

### Implementation Path

1. Introduce SQLAlchemy/SQLModel as abstraction layer over database access
2. Swap dialect from `sqlite://` to `postgresql://`
3. Add Alembic migrations for schema versioning
4. Test against both backends during transition

## 6. LLM Safety Enhancements

### Confidence Gating

Reject low-confidence outputs (e.g., `confidence_score < 0.6`) and prompt the FSM to refine their query rather than executing potentially incorrect SQL.

### Retry Budget

Implement a per-session retry budget (e.g., 5 retries before escalation) to prevent infinite retry loops when the LLM produces repeatedly invalid output.

### Structured Output Validation

The current output validator in `copilot.py` runs SQL through `LIMIT 0` validation. Add:
- Column-name verification against schema (reject hallucinated columns)
- Table-existence check (reject hallucinated tables)
- Join-path validation (reject joins on non-foreign-key columns)

### Implementation Path

1. Extend `validate_explore_sql` with schema-grounded checks
2. Add `retry_budget` to `AgentDependencies` with per-session counter
3. Wire confidence threshold as configurable parameter in `Settings`
4. Add test cases for each safety scenario in the evaluation suite

## 7. Deployment

### Containerisation

```dockerfile
# Backend
FROM python:3.12-slim
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen
COPY backend/app ./app
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Frontend
FROM node:20-alpine
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci && npm run build
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
```

### Infrastructure

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Container orchestrator | Kubernetes / ECS | Scalable, zero-downtime deployments |
| Reverse proxy | Traefik / Nginx | TLS termination, path-based routing |
| Secret management | Vault / AWS Secrets Manager | API keys, DB credentials, Langfuse keys |
| CI/CD | GitHub Actions | Automated tests on PR, deploy on merge |

## 8. Estimated Effort

| Workstream | Effort | Priority |
|------------|--------|----------|
| Authentication (OIDC + roles) | 3-5 days | P0 |
| Rate limiting | 1-2 days | P0 |
| Monitoring + dashboards | 2-3 days | P1 |
| Rule review workflow | 5-7 days | P1 |
| Database migration (PostgreSQL) | 3-5 days | P2 |
| LLM safety enhancements | 2-3 days | P1 |
| Containerisation + CI/CD | 2-3 days | P1 |
| **Total** | **~3-5 weeks** | |