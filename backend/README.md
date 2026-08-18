# Backend

FastAPI + LangGraph backend for the Fraud Insight & Rule Copilot.
Python 3.12, managed with [uv](https://docs.astral.sh/uv/).

## Run

```bash
uv sync
uv run python -m uvicorn app.main:app --reload --port 8000
```

- `GET /api/health` — liveness
- `GET /api/health/ready` — LLM + Langfuse configuration state
- `GET /docs` — OpenAPI

## Layout

```
app/
  main.py             FastAPI app, health endpoints, CORS, lifespan
  common/
    settings.py       pydantic-settings configuration (env-driven)
    model.py          get_model() — provider-agnostic LLM loading
    logger.py         Structured JSON logging to stdout
    observability.py  Langfuse tracing seam (callbacks, health, flush)
    visualize.py      LangGraph → Mermaid diagram helper
data/
  data.db             Dev transaction dataset (tracked: only copy of the data)
  sessions.db         Session persistence store
  schema.sql          Reference schema DDL (basis for the seed script)
```

## Configuration

Copy `.env.example` to `.env`. Ollama is the default provider; hosted
providers (OpenAI, Anthropic) require `LLM_API_KEY`. Langfuse tracing is
optional — without keys every observability call is a no-op.

## Quality

`ruff` (lint + format, config in `pyproject.toml`) and `mypy` are the
intended gates:

```bash
uv run ruff check app
uv run ruff format --check app
uv run mypy app
```
