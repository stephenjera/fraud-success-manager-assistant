"""
D-6: Unified eval script entrypoint.

Usage:
    python -m tests.evaluate --offline    # D-7 only (fast, no server/LLM)
    python -m tests.evaluate --online     # D-1 through D-5 (needs running backend)
    python -m tests.evaluate              # Both offline + online
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time


def run_offline_tests() -> tuple[bool, float]:
    """
    Run D-7 safety guardrail unit tests via pytest.
    Returns (all_passed, elapsed_seconds).
    """
    print("=" * 60)
    print("OFFLINE EVALUATION — D-7: Safety Guardrails")
    print("=" * 60)

    start = time.perf_counter()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_safety_guardrails.py",
            "-v",
            "--tb",
            "short",
            "-q",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    elapsed = time.perf_counter() - start

    print(result.stderr)
    print(result.stdout)

    passed = result.returncode == 0

    if passed:
        print("[OK] All safety guardrail tests passed.")
    else:
        print("[FAIL] Some safety guardrail tests failed.")

    return passed, elapsed


def run_online_eval(limit: int | None) -> bool:
    """
    Run online evaluation: D-2, D-3, D-4, D-5 via scorer module.
    Returns True if at least some results were produced.
    """
    print()
    print("=" * 60)
    print("ONLINE EVALUATION — D-1 through D-5")
    if limit:
        print(f"Limiting to first {limit} test pairs")
    print("=" * 60)

    start = time.perf_counter()

    try:
        from tests.evaluate.scorer import print_summary, run_online_eval as scorer_run

        summary = scorer_run(skip_rule_eval=False, limit=limit)
        result_dict = print_summary(summary)
        elapsed = time.perf_counter() - start

        print()
        print(f"Online eval completed in {elapsed:.1f}s")
        print(f"Executed {summary.total_pairs} NL->SQL pairs")

        return summary.total_pairs > 0

    except RuntimeError as exc:
        print(f"[ERROR] Online eval failed: {exc}")
        return False
    except ConnectionError as exc:
        print(f"[ERROR] Connection failed: {exc}")
        print("  Ensure the backend is running: uvicorn app.main:app --port 8000")
        return False


def print_final_report(
    offline_passed: bool | None,
    offline_elapsed: float | None,
    online_completed: bool | None,
) -> None:
    print()
    print("=" * 60)
    print("EVALUATION REPORT")
    print("=" * 60)

    print(f"  D-7 Safety Guardrails:    {'PASS' if offline_passed else 'FAIL'}", end="")
    if offline_passed and offline_elapsed is not None:
        print(f" ({offline_elapsed:.1f}s)")
    print()

    print(f"  D-1 Test Dataset:         Available (20 pairs)", end="")
    print()

    if online_completed is not None:
        print(f"  D-2 Execution Accuracy:   {'Evaluated' if online_completed else 'SKIPPED'}", end="")
        print()
        print(f"  D-3 Query Validity:       {'Evaluated' if online_completed else 'SKIPPED'}", end="")
        print()
        print(f"  D-4 Latency (p50/p95):    {'Evaluated' if online_completed else 'SKIPPED'}", end="")
        print()
        print(f"  D-5 Rule Metrics:         {'Evaluated' if online_completed else 'SKIPPED'}", end="")
        print()
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FSM Assistant Evaluation Suite",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run only offline tests (D-7 safety guardrails, fast, no LLM needed)",
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="Run online NL->SQL evaluation (requires running backend at :8000)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit online eval to first N test pairs (e.g. --limit 5)",
    )
    parser.add_argument(
        "--skip-rule-eval",
        action="store_true",
        help="Skip D-5 rule precision/recall evaluation",
    )

    args = parser.parse_args()

    run_offline = args.offline or not args.online
    run_online = args.online or not args.offline

    offline_passed: bool | None = None
    offline_elapsed: float | None = None
    online_completed: bool | None = None

    if run_offline:
        offline_passed, offline_elapsed = run_offline_tests()

    if run_online:
        online_completed = run_online_eval(args.limit)

    print_final_report(offline_passed, offline_elapsed, online_completed)


if __name__ == "__main__":
    main()
