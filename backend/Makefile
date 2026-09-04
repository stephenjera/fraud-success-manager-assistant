.PHONY: lint test eval eval-llm up migrate seed api

# Promptfoo version the three LLM suites were verified against.
PROMPTFOO ?= npx -y promptfoo@0.122.2

lint:
	uv run ruff check
	uv run ruff format --check
	uv run mypy app

test:
	uv run pytest

eval:
	uv run python eval/harness.py -q

# LLM suites (NL->SQL accuracy, explanation faithfulness, safety/refusal) against
# the live agent API. Requires the API running (default 127.0.0.1:8000) and the
# Ollama judge model (default gemma4:26b, overridable via JUDGE_MODEL). Sequential
# (-j 1) to avoid overloading the agent/Ollama; the venv leads PATH so promptfoo's
# python assertions can import psycopg.
eval-llm:
	@EVAL_API_BASE=$(if $(EVAL_API_BASE),$(EVAL_API_BASE),http://127.0.0.1:8000) \
	PATH="./.venv/bin:$$PATH" PROMPTFOO_PYTHON="./.venv/bin/python" \
	$(PROMPTFOO) eval -c eval/promptfoo/nl2sql.yaml --no-cache -j 1
	@EVAL_API_BASE=$(if $(EVAL_API_BASE),$(EVAL_API_BASE),http://127.0.0.1:8000) \
	PATH="./.venv/bin:$$PATH" PROMPTFOO_PYTHON="./.venv/bin/python" \
	$(PROMPTFOO) eval -c eval/promptfoo/faithfulness.yaml --no-cache -j 1
	@EVAL_API_BASE=$(if $(EVAL_API_BASE),$(EVAL_API_BASE),http://127.0.0.1:8000) \
	PATH="./.venv/bin:$$PATH" PROMPTFOO_PYTHON="./.venv/bin/python" \
	$(PROMPTFOO) eval -c eval/promptfoo/safety.yaml --no-cache -j 1

up:
	docker compose -f ../docker-compose.yml up -d --build

migrate:
	uv run alembic upgrade head

seed:
	uv run python scripts/seed_reference.py

api:
	uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
