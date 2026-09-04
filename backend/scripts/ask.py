"""Grounded Q&A probe: ask the fraud agent a couple of questions and log the answers.

This is a behavior probe, not a test suite. Every request/response (status +
pretty-printed body) is printed to stdout — redirect to a file to capture:

    uv run python scripts/ask.py > logs/ask.log 2>&1
"""

# ruff: noqa: INP001  # standalone probe script, not a package

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

BASE = "http://127.0.0.1:8012"

# A small set of probes that each force the agent to ground itself in the data.
QUESTIONS = [
    (
        "How many transactions are there in total, and how many are labeled fraud? "
        "What is the baseline fraud rate?"
    ),
    "Which MCC codes have the highest fraud rate among those with at least 1,000 transactions?",
]


def log(message: str = "") -> None:
    """Print a timestamped, flushed log line."""
    line = f"[{datetime.now(UTC).strftime('%H:%M:%S')}] {message}"
    print(line, flush=True)


def call(
    method: str, path: str, body: dict | None = None, timeout: int = 1800
) -> tuple[int, object]:
    """Issue one HTTP call and log the request, status, timing, and full body."""
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    log(f">>> {method} {url}")
    start = time.monotonic()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    except Exception as exc:  # noqa: BLE001 - probe must log, never crash mid-run
        log(f"    !! transport error after {time.monotonic() - start:.1f}s: {exc!r}")
        return -1, {"error": repr(exc)}
    try:
        parsed: object = json.loads(raw)
    except json.JSONDecodeError:
        parsed = raw.decode(errors="replace")
    log(f"<<< {status} in {time.monotonic() - start:.1f}s")
    pretty = (
        json.dumps(parsed, indent=2, default=str)
        if isinstance(parsed, object)
        else str(parsed)
    )
    log("    " + "\n    ".join(pretty.splitlines()))
    return status, parsed


def as_dict(value: object) -> dict:
    """Coerce a response body to a dict (defensive)."""
    return value if isinstance(value, dict) else {}


def main() -> None:
    """Create a conversation, ask each probe question, and log the grounded answers."""
    log("=" * 60)
    log("FRAUD AGENT — GROUNDED Q&A PROBE")
    log("=" * 60)

    call("GET", "/api/health")
    call("GET", "/api/health/ready")

    _, conv_body = call("POST", "/api/conversations")
    conversation_id = as_dict(conv_body).get("id", "conv-unknown")
    log(f"conversation: {conversation_id}")

    for question in QUESTIONS:
        call(
            "POST",
            f"/api/conversations/{conversation_id}/messages",
            {"text": question},
        )

    call("GET", f"/api/conversations/{conversation_id}")
    log("=" * 60)
    log("PROBE COMPLETE")
    log("=" * 60)


if __name__ == "__main__":
    main()
