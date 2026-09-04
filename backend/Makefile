.PHONY: lint test eval up migrate seed api

lint:
	uv run ruff check
	uv run ruff format --check
	uv run mypy app

test:
	uv run pytest

eval:
	uv run python eval/harness.py -q

up:
	docker compose -f ../docker-compose.yml up -d --build

migrate:
	uv run alembic upgrade head

seed:
	uv run python scripts/seed_reference.py

api:
	uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
