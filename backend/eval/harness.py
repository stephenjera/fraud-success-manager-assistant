"""Deterministic eval runner.

Runs the pytest subset (validator, flags, backtest math, rule state, rule
engine) and returns its exit code. It is `make eval` — the no-LLM gate.

The LLM-evaluated suites (NL→SQL accuracy, explanation faithfulness,
safety/refusal) live in `eval/promptfoo/` (nl2sql.yaml, faithfulness.yaml,
safety.yaml) and run separately via `make eval-llm` against the live agent
API with an Ollama judge (see docs/architecture/eval-design.md).
"""

from __future__ import annotations

import subprocess
import sys

_TESTS = [
    "tests/test_sql_validator.py",
    "tests/test_flags.py",
    "tests/test_backtest_math.py",
    "tests/test_rule_state.py",
    "tests/test_rule_engine.py",
    "tests/test_architecture.py",
]


def run() -> int:
    """Run the deterministic eval suite and return 0 on success."""
    cmd = [sys.executable, "-m", "pytest", "-q", *_TESTS]
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    sys.exit(run())
