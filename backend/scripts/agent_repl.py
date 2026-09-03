"""Interactive REPL: watch the *real* LLM agent run one question at a time.

Unlike ``e2e_walktalk.py --live`` (a fixed 23-step walk with asserts), this is a
free terminal for *seeing* what the model actually does -- which columns it
profiles, what SQL it writes, the flags it raises, and the grounded answer.

It drives the real FastAPI app in-process (``TestClient``), so everything after
the LLM (validation reader, backtest, Postgres) is genuinely exercised. Only the
provider call is the real thing: Ollama at ``settings.llm_api_base``.

Run (from ``backend/``):

    .venv/bin/python scripts/agent_repl.py [initial question text]

Commands: ``exit`` / ``quit`` / ``:q`` to leave; ``:help`` for this list.
"""

# ruff: noqa: INP001  # standalone probe script, not a package

from __future__ import annotations

import json
import os
import re
import sys
import time

# Make ``app`` importable regardless of the caller's CWD / sys.path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point the app at a real Ollama model and disable Langfuse. Must be set before
# ``app.common.settings`` is imported (Pydantic reads it there). No fakes.
os.environ.setdefault("LLM_PROVIDER", "ollama")
os.environ.setdefault("LLM_MODEL", os.environ.get("LIVE_MODEL", "qwen3.8:27b-128k"))
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""

import time  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.common.settings import settings  # noqa: E402
from app.main import create_app  # noqa: E402

client = TestClient(create_app())


# ---------------------------------------------------------------------------
def _sse(text: str) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for block in re.split(r"\n\n+", text or ""):
        block = block.strip()
        if not block:
            continue
        event, data = "message", ""
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data += line[len("data: "):]
        if data:
            out.append((event, json.loads(data)))
    return out


def ask(text: str) -> None:
    cid = client.post("/v1/conversations").json()["conversation_id"]

    m = client.post(f"/v1/conversations/{cid}/messages", json={"text": text})
    mid, run_id = m.json()["message_id"], m.json()["run_id"]

    print(f"\n> {text}")
    print(f"  [conversation {cid[:8]} | message {mid[:8]} | run {run_id[:8]}]")

    # The LLM turn runs on a worker thread. The *streaming* /events endpoint blocks
    # while the run is in flight (it waits on a live asyncio queue) — so poll the
    # durable message row (a dict lookup) until terminal, exactly like the walk.
    msg_url = f"/v1/conversations/{cid}/messages/{mid}"
    deadline = time.monotonic() + float(os.environ.get("LIVE_TIMEOUT_S", "240"))
    body = {}
    while time.monotonic() < deadline:
        body = client.get(msg_url).json()
        if body.get("status") in ("success", "error"):
            break
        time.sleep(0.25)
    else:
        print("  (timed out waiting for the run to reach a terminal status)")

    # Now the run is terminal: /events replays from the ring buffer and returns
    # immediately (no live wait). This is what the walk does in step 5.
    raw = client.get(f"/v1/runs/{run_id}/events")
    events = _sse(raw.text) if raw.status_code == 200 else []
    for name, data in events:
        if name == "tool_call.start":
            args = data.get("args", {})
            pretty = " ".join(str(v) for v in args.values())
            print(f"  -- tool {data.get('tool')}( {pretty[:300]} )")
        elif name == "tool_call.done":
            summary = str(data.get("result_summary", ""))
            print(f"  -- {data.get('tool')} -> {summary[:300]}")
        elif name == "message.delta":
            print(f"  ## {str(data.get('delta', ''))[:1200]}")
        elif name == "run.done":
            print(f"  == run.done  {data.get('tokens_in')} in / {data.get('tokens_out')} out  "
                  f"{(data.get('duration_ms') or 0) / 1000:.1f}s")
        elif name == "run.error":
            print(f"  !! run.error  {data.get('detail')}")

    # The durable, canonical answer lives on the stored message (ADR-0011).
    g = body.get("grounding") or {}
    if g:
        print("\n  ANSWER")
        print(f"    sql        : {g.get('sql')}")
        print(f"    tables     : {', '.join(g.get('tables_and_joins_used') or [])}")
        if g.get("flags"):
            print(f"    flags      : {json.dumps(g.get('flags'))}")
        print(f"    assumpt.   : {json.dumps(g.get('assumptions') or [])}")
    if body.get("error"):
        e = body.get("error") or {}
        print(f"\n  REFUSED -- code  : {e.get('code')}")
        print(f"  message  : {e.get('message')}")
        print(f"  reason   : {(e.get('details') or {}).get('error')}")
        print("  try      : a question about the reference tables above "
              "(transactions, fraud_labels, cards, merchants, users, mcc_codes, "
              "merchant_locations)")


HELP = ("Type a question about the fraud dataset (e.g. 'How many high-value\n"
        "transactions are there?'). Commands: :help, exit / quit / :q.")


def _reference_tables() -> list[str]:
    """Reflect the reference schema (graceful on no DB / no role access)."""
    try:
        import psycopg

        con = psycopg.connect(settings.reference_dsn, autocommit=True)
        try:
            with con.cursor() as cur:
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'reference' ORDER BY table_name"
                )
                return [r[0] for r in cur.fetchall()]
        finally:
            con.close()
    except Exception:  # noqa: BLE001 - capability banner must never block the REPL
        return []


def main() -> int:
    print("Fraud agent REPL -- live LLM ({}).".format(settings.llm_model))
    tables = _reference_tables()
    if tables:
        print("Answers questions you can ground in these tables:")
        print("  " + ", ".join(tables) + "\n")
    print(HELP + "\n")

    seed = sys.argv[1] if len(sys.argv) > 1 else None
    if seed:
        ask(seed)

    while True:
        try:
            line = input("\nquestion> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            break
        if not line:
            continue
        if line.lower() in ("exit", "quit", ":q", ":quit"):
            print("bye")
            break
        if line in (":help", "help"):
            print(HELP)
            continue
        ask(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
