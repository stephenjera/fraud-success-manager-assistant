"""Slim eval harness that replaces promptfoo.

Runs the deterministic pytest subset (validator, flags, backtest math,
rule state, rule engine) and prints a summary. The LLM-evaluated suites
(NL→SQL accuracy, explanation faithfulness, safety/refusal) are deferred
until a judge model is available — they are documented in eval-design.md
but not wired here (no promptfoo dependency, per P4 decision).
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
