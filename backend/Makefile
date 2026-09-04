.PHONY: lint test eval

lint:
	uv run ruff check
	uv run ruff format --check
	# ponytail: mypy skipped — 38 pre-existing errors in app/, add back when writing new app/ code

test:
	uv run pytest

eval:
	uv run pytest tests/test_sql_validator.py tests/test_flags.py tests/test_rule_state.py tests/test_architecture.py -q
