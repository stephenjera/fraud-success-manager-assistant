"""Headless E2E walkthrough of the FSM rule lifecycle (docs/architecture/e2e-walktalk.md).

Drives the *real* API -- routers -> services -> core -> Postgres + the ``reference``
tables -- in the exact order a real analyst would, and asserts the *shape* of every
response (the frozen contract, not the LLM's content). The LLM and the synchronous
reader are faked (the same two seams ``tests/conftest.py`` uses) so the walk is
deterministic; the **backtest still runs the rule's clause against real data**.

Run (from ``backend/``):

    .venv/bin/python scripts/e2e_walktalk.py

Exit code 0 when every step's shape holds. On the first failure it prints the step
number, the method + URL, the request body, and the response, then exits 1.

This is the *shape* suite in ``make eval`` -- distinct from ``pytest`` (deterministic
logic + the ADR-0005 wall) and from promptfoo (LLM content / correctness). Phases
1-6 of the walk are driven; the Phase-7 failure path is intentionally skipped (the
spec: it needs a red-team fixture, not this script).
"""

# ruff: noqa: INP001  # standalone probe script, not a package

from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --live points the app at a real Ollama model and disables Langfuse tracing.
# Must be set before ``app.common.settings`` is imported (Pydantic reads it there).
LIVE = "--live" in sys.argv
if LIVE:
    os.environ.setdefault("LLM_PROVIDER", "ollama")
    os.environ.setdefault("LLM_MODEL", "qwen3.8:27b-128k")
    os.environ["LANGFUSE_PUBLIC_KEY"] = ""
    os.environ["LANGFUSE_SECRET_KEY"] = ""

# ---------------------------------------------------------------------------
# Fake seams -- the LLM is a stand-in; the backtest reads real reference data.
# Installed before the first HTTP call so ``run.execute`` (worker thread) sees them.
# Skipped in --live mode: there the *real* LLM (Ollama) and *real* reference
# reader are the thing under test. The **backtest still runs real reference data**
# in both modes (ADR-0014), since it never touches the LLM.
# ---------------------------------------------------------------------------

from app.core import db as core_db  # noqa: E402
from app.core import flags as core_flags  # noqa: E402
from app.services import run as run_service  # noqa: E402

FAKE_GROUNDING = {
    "sql": "SELECT COUNT(*) AS total_transactions FROM transactions;",
    "explanation": "1,159,966 transactions in the dataset.",
    "assumptions": ["Counted all rows; no filters applied."],
    "tables_and_joins_used": ["transactions"],
    "flags": [],
}

_TOOL_OUT = '{"columns": ["total_transactions"], "rows": [[1159966]], "row_cap": 100, "truncated": false}'


class _FakeGraph:
    """A compiled-graph stand-in: emit one ``run_sql`` tool callback, return a grounded answer."""

    def invoke(self, state: dict, config: dict) -> dict:
        for handler in (config or {}).get("callbacks", []) or []:
            if hasattr(handler, "on_tool_start"):
                handler.on_tool_start(
                    {"name": "run_sql"},
                    '{"sql": "SELECT COUNT(*) FROM transactions"}',
                    run_id="fake-tool-run",
                )
                handler.on_tool_end(_TOOL_OUT, run_id="fake-tool-run")
        return {"messages": [], "grounding": dict(FAKE_GROUNDING)}


def _fake_reader(sql_text: str) -> core_flags.Result:  # noqa: ARG001 - deterministic stand-in
    return core_flags.Result(
        columns=["total_transactions"], rows=[[1159966]], row_cap=100, truncated=False
    )


if not LIVE:
    run_service._graph = lambda: _FakeGraph()  # noqa: SLF001 - the seam conftest also patches
    run_service.get_tracing_callbacks = lambda: []
    core_db.run_readonly_query = _fake_reader
    core_db.count_rows = lambda table: 1159966  # noqa: ARG005

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402

# ---------------------------------------------------------------------------
# Walk driver
# ---------------------------------------------------------------------------


class StepFailure(Exception):
    """A failed step, carrying everything the spec says to print on failure."""

    def __init__(
        self, step: int, method: str, url: str, request: Any, status: int, body: Any
    ) -> None:
        self.step = step
        self.method = method
        self.url = url
        self.request = request
        self.status = status
        self.body = body
        super().__init__(f"step {step}: {method} {url}")


class Walk:
    """Drive the API in order; record every step; assert the frozen shape at each."""

    LIVE_TIMEOUT_S = 240.0  # a 27B model can take a while for one multi-tool turn

    def __init__(self, client: TestClient, *, live: bool = False) -> None:
        self.c = client
        self.live = live
        self.passed: list[int] = []
        self._last: tuple[int, str, str, Any] = (0, "", "", None)

    def call(
        self,
        step: int,
        method: str,
        url: str,
        body: Any = None,
        *,
        expect: int | None = None,
    ) -> Any:
        """One API call: dispatch, check status (if given), return the JSON body."""
        self._last = (step, method, url, body)
        try:
            if method == "GET":
                r = self.c.get(url)
            elif method == "POST":
                r = self.c.post(url, json=body)
            elif method == "PATCH":
                r = self.c.patch(url, json=body)
            else:
                raise AssertionError(f"unsupported method {method}")
        except Exception as exc:  # noqa: BLE001 - a transport error is a step failure
            raise StepFailure(step, method, url, body, -1, repr(exc)) from exc
        if expect is not None and r.status_code != expect:
            try:
                payload: Any = r.json()
            except json.JSONDecodeError:
                payload = r.text
            raise StepFailure(step, method, url, body, r.status_code, payload)
        self.passed.append(step)
        try:
            return r.json()
        except json.JSONDecodeError:
            return r.text

    # -- shape helpers ------------------------------------------------------

    @staticmethod
    def _has(body: Any, *keys: str) -> Any:
        if not isinstance(body, dict) or any(k not in body for k in keys):
            found = (
                sorted(body.keys()) if isinstance(body, dict) else type(body).__name__
            )
            raise AssertionError(f"missing key(s) {keys}; got: {found}")
        return body

    @staticmethod
    def _is_list(body: Any) -> None:
        if not isinstance(body, dict) or not isinstance(body.get("items"), list):
            raise AssertionError("expected an envelope with a list 'items'")

    @staticmethod
    def _sse(text: str) -> list[tuple[str, dict]]:
        out: list[tuple[str, dict]] = []
        for block in re.split(r"\n\n+", text or ""):
            block = block.strip()
            if not block:
                continue
            event, data = "message", ""
            for line in block.splitlines():
                if line.startswith("event: "):
                    event = line[len("event: ") :]
                elif line.startswith("data: "):
                    data += line[len("data: ") :]
            if data:
                out.append((event, json.loads(data)))
        return out

    def wait_until_terminal(self, cid: str, mid: str) -> Any:
        """Poll the message until it is no longer ``running`` (the fake finishes fast)."""
        url = f"/v1/conversations/{cid}/messages/{mid}"
        deadline = time.monotonic() + (self.LIVE_TIMEOUT_S if self.live else 20)
        while time.monotonic() < deadline:
            body = self.c.get(url).json()
            if body["status"] in ("success", "error"):
                return body
            time.sleep(0.1)
        self._last = (6, "GET", url, None)
        raise StepFailure(
            6,
            "GET",
            url,
            None,
            -2,
            {"error": "timed out waiting for the run to reach a terminal status"},
        )


# ---------------------------------------------------------------------------
# The walk (phases 1-6 of e2e-walktalk.md)
# ---------------------------------------------------------------------------


def run_walk(w: Walk) -> None:
    c = w.c

    # ----- Phase 1: session start ------------------------------------------
    body = w.call(1, "GET", "/v1/health/ready", expect=200)
    w._has(body, "ready", "llm", "db")
    if not isinstance(body["ready"], bool):
        raise AssertionError("'ready' must be a bool")

    body = w.call(2, "GET", "/v1/conversations", expect=200)
    w._is_list(body)
    w._has(body, "page", "page_size", "token")

    body = w.call(3, "POST", "/v1/conversations", expect=201)
    w._has(body, "conversation_id", "created_at")
    cid = body["conversation_id"]

    # ----- Phase 2: first grounded turn (NL -> SQL) ------------------------
    body = w.call(
        4,
        "POST",
        f"/v1/conversations/{cid}/messages",
        {"text": "How many transactions are there?"},
        expect=201,
    )
    w._has(body, "message_id", "run_id", "status")
    if body["status"] != "running":
        raise AssertionError("POST /messages must return the command (status=running)")
    mid, run_id = body["message_id"], body["run_id"]

    w.wait_until_terminal(cid, mid)

    w._last = (5, "GET", f"/v1/runs/{run_id}/events", None)
    raw = c.get(f"/v1/runs/{run_id}/events")
    if raw.status_code != 200:
        raise StepFailure(
            5, "GET", f"/v1/runs/{run_id}/events", None, raw.status_code, raw.text
        )
    events = w._sse(raw.text)
    names = [e for e, _ in events]
    if not names or names[0] != "run.start" or names[-1] != "run.done":
        raise AssertionError(
            f"SSE must open with run.start and close with run.done: {names}"
        )
    for need in ("tool_call.start", "tool_call.done", "message.delta"):
        if need not in names:
            raise AssertionError(f"SSE missing required event {need!r}: {names}")
    if names.index("tool_call.start") > names.index("tool_call.done"):
        raise AssertionError("tool_call.start must precede tool_call.done")
    if names.count("run.start") != 1 or names.count("run.done") != 1:
        raise AssertionError("SSE must emit exactly one run.start and one run.done")
    if "run.error" in names:
        raise AssertionError("a clean run must not emit run.error")
    w.passed.append(5)

    body = w.call(6, "GET", f"/v1/conversations/{cid}/messages/{mid}", expect=200)
    w._has(body, "message_id", "run_id", "status", "grounding", "error", "revisions")
    if (
        body["status"] != "success"
        or body["grounding"] is None
        or body["error"] is not None
    ):
        raise AssertionError(
            f"message must be success + grounding + null error; status={body['status']}"
        )
    w._has(
        body["grounding"],
        "sql",
        "explanation",
        "assumptions",
        "tables_and_joins_used",
        "flags",
    )
    if not body["revisions"]:
        raise AssertionError("a succeeded agent turn must carry at least one revision")

    if LIVE:
        # The LLM's own provenance: token counts (the fake graph returns 0/0) and the
        # tool calls + grounded SQL. A real run has tokens_in/out > 0 and a non-canned explanation.
        tokens = next((d for e, d in events if e == "run.done"), {})
        g = body["grounding"]
        tools = [
            f"{d.get('tool')}({d.get('args')})"
            for e, d in events
            if e == "tool_call.start"
        ]
        print("\n--- LIVE LLM EVIDENCE (step 6: the real agent turn) ---")
        print(
            f"  tokens   : {tokens.get('tokens_in')} in / {tokens.get('tokens_out')} out  "
            f"(0/0 would be the fake graph)"
        )
        print(f"  tool calls: {tools or '(none — the model answered without run_sql)'}")
        print(f"  sql      : {g.get('sql')}")
        print(f"  expl     : {str(g.get('explanation'))[:300]}")
        fake_marker = "1,159,966 transactions in the dataset."
        if int(tokens.get("tokens_out", 0) or 0) == 0 and fake_marker in str(
            g.get("explanation")
        ):
            raise AssertionError(
                "the run used the FAKE LLM seam, not a real model (0 tokens + canned prose)"
            )
        print("------------------------------------------------------------\n")

    # ----- Phase 3: edit + re-run (the FSM owns the SQL) -------------------
    # The FSM's edited query; its WHERE is what becomes the rule's clause.
    fsm_sql = "SELECT COUNT(*) AS high_value FROM transactions WHERE amount_usd_cents > 100000"
    body = w.call(
        8,
        "POST",
        f"/v1/conversations/{cid}/messages/{mid}/rerun",
        {"sql": fsm_sql},
        expect=200,
    )
    w._has(body, "message_id", "revision_id", "result", "flags")
    w._has(body["result"], "columns", "rows", "row_cap", "truncated")
    rev2 = body["revision_id"]

    body = w.call(9, "GET", f"/v1/conversations/{cid}/messages/{mid}", expect=200)
    if not isinstance(body["revisions"], list) or len(body["revisions"]) < 2:
        raise AssertionError("after a rerun the message must carry >= 2 revisions")
    if body["revisions"][0] != rev2:
        raise AssertionError("revisions must be newest-first (the rerun on top)")

    # ----- Phase 4: pin the insight (the bridge) ----------------------------
    body = w.call(
        10,
        "POST",
        f"/v1/conversations/{cid}/insights",
        {
            "message_id": mid,
            "revision_id": rev2,
            "sql": fsm_sql,
            "explanation": "High-value transactions.",
        },
        expect=201,
    )
    w._has(body, "insight_id")
    insight_id = body["insight_id"]

    body = w.call(11, "GET", f"/v1/conversations/{cid}/insights", expect=200)
    w._is_list(body)
    if not any(item.get("insight_id") == insight_id for item in body["items"]):
        raise AssertionError("the right rail must contain the pinned insight")

    body = w.call(12, "GET", f"/v1/insights/{insight_id}", expect=200)
    w._has(body, "insight_id", "message_id", "revision_id", "sql")

    # ----- Phase 5: draft + backtest ---------------------------------------
    body = w.call(13, "POST", f"/v1/insights/{insight_id}/draft-rule", expect=201)
    w._has(body, "rule_id", "draft_where", "rationale", "assumptions")
    rule_id = body["rule_id"]

    body = w.call(14, "GET", f"/v1/rules/{rule_id}", expect=200)
    w._has(body, "rule_id", "source_insight_id", "where_clause", "status", "created_by")
    if body["status"] != "draft":
        raise AssertionError(
            f"a freshly drafted rule must be 'draft', got {body['status']}"
        )

    # edit-and-own, still legal (no backtest row yet)
    body = w.call(
        15,
        "PATCH",
        f"/v1/rules/{rule_id}",
        {"where_clause": "amount_usd_cents > 200000"},
        expect=200,
    )
    if body.get("status") != "draft":
        raise AssertionError("PATCH pre-backtest must leave the rule in 'draft'")
    if body.get("where_clause") != "amount_usd_cents > 200000":
        raise AssertionError(
            f"PATCH must persist the new clause; got {body.get('where_clause')!r}"
        )

    # the backtest runs the clause against real reference data (ADR-0014 two universes).
    body = w.call(16, "POST", f"/v1/rules/{rule_id}/backtest", expect=201)
    w._has(
        body,
        "backtest_id",
        "rule_id",
        "window",
        "where_clause",
        "labeled_only",
        "full_universe",
        "temporal_stability",
        "sample",
    )
    for uni in ("labeled_only", "full_universe"):
        w._has(body[uni], "confusion_matrix", "metrics", "coverage")
        w._has(body[uni]["confusion_matrix"], "tp", "fp", "fn", "tn")
        w._has(
            body[uni]["metrics"],
            "precision",
            "recall",
            "false_positive_rate",
            "baseline_fraud_rate",
            "lift",
        )
        w._has(
            body[uni]["coverage"],
            "matched_count",
            "total_rows",
            "total_fraud",
            "support",
        )
    if (
        not isinstance(body["temporal_stability"], dict)
        or not body["temporal_stability"]
    ):
        raise AssertionError("backtest must carry a non-empty temporal_stability block")
    w._has(body["sample"], "count", "columns", "rows")
    if body["sample"]["count"] != len(body["sample"]["rows"]):
        raise AssertionError("sample.count must equal the number of sample rows")
    backtest_id = body["backtest_id"]

    # 16a: the freeze line -- a WHERE edit after a backtest row exists (409).
    w._last = (
        16,
        "PATCH",
        f"/v1/rules/{rule_id}",
        {"where_clause": "amount_usd_cents > 999999999"},
    )
    frozen = c.patch(
        f"/v1/rules/{rule_id}", json={"where_clause": "amount_usd_cents > 999999999"}
    )
    if (
        frozen.status_code != 409
        or frozen.json()["error"]["code"] != "RULE_ILLEGAL_TRANSITION"
    ):
        raise StepFailure(
            16,
            "PATCH",
            f"/v1/rules/{rule_id}",
            {"where_clause": "amount_usd_cents > 999999999"},
            frozen.status_code,
            frozen.json(),
        )

    body = w.call(17, "GET", f"/v1/rules/{rule_id}/backtests", expect=200)
    w._is_list(body)
    if not any(item.get("backtest_id") == backtest_id for item in body["items"]):
        raise AssertionError("the tuning history must contain the backtest just run")

    body = w.call(18, "GET", f"/v1/rules/{rule_id}/backtests/{backtest_id}", expect=200)
    w._has(
        body,
        "backtest_id",
        "rule_id",
        "window",
        "labeled_only",
        "full_universe",
        "temporal_stability",
        "sample",
    )

    # ----- Phase 6: approve -> deploy -> catalog ----------------------------
    body = w.call(
        19,
        "POST",
        f"/v1/rules/{rule_id}/approve",
        {
            "rationale": "precision acceptable; sample rows consistent with a fraud profile.",
            "actor": "fsm-placeholder-1",
        },
        expect=200,
    )
    w._has(body, "rule_id", "status", "approved_by", "approved_at", "rationale")
    if body["status"] != "approved":
        raise AssertionError(
            f"approve must move the rule to 'approved', got {body['status']}"
        )

    body = w.call(20, "POST", f"/v1/rules/{rule_id}/deploy", expect=201)
    w._has(body, "deployment_id", "external_rule_id")

    body = w.call(21, "GET", f"/v1/rules/{rule_id}/deployment", expect=200)
    w._has(body, "rule_id", "deployment", "status")
    if body["status"] != "deployed" or body["deployment"] is None:
        raise AssertionError(f"deployment read must show deployed + a record: {body}")

    # the catalog (cross-conversation). Post-deploy the rule is 'deployed'; the
    # unfiltered catalog must still expose it -- the shape allows any status.
    body = w.call(22, "GET", "/v1/rules", expect=200)
    w._is_list(body)
    if not any(item.get("rule_id") == rule_id for item in body["items"]):
        raise AssertionError("the catalog must expose the rule")

    body = w.call(23, "POST", f"/v1/rules/{rule_id}/disable", expect=200)
    w._has(body, "rule_id", "deployment_id", "disabled_at")


def _report_failure(exc: StepFailure) -> int:
    bar = "=" * 72
    print(f"\n{bar}\nWALK FAILED at step {exc.step}\n{bar}")
    print(f"  {exc.method}  {exc.url}")
    print(f"  request : {json.dumps(exc.request, default=str)[:600]}")
    print(f"  status  : {exc.status}")
    snippet = (
        exc.body
        if isinstance(exc.body, (str, list))
        else json.dumps(exc.body, default=str, indent=2)
    )
    print(f"  response:\n{(snippet or '')[:2000]}")
    print(bar + "\n")
    return 1


def main() -> int:
    if LIVE:
        print(
            "LIVE mode: real LLM (Ollama) + real reference reader; shape-only asserts."
        )
        print(
            "Note: the agent's own SQL is non-deterministic -- exact metric numbers\n"
            "vary run to run. The pass bar is the *shape* of the frozen contract.\n"
        )
    started = time.monotonic()
    w = Walk(TestClient(create_app()), live=LIVE)
    try:
        run_walk(w)
    except StepFailure as exc:
        return _report_failure(exc)
    except AssertionError as exc:
        step, method, url, body = w._last
        return _report_failure(
            StepFailure(step, method, url or "<shape check>", body, -2, str(exc))
        )
    except Exception:  # noqa: BLE001
        print("\nWALK crashed with an unhandled exception:")
        traceback.print_exc()
        return 2

    elapsed = time.monotonic() - started
    steps = ", ".join(str(s) for s in w.passed)
    prefix = "LIVE WALK PASSED" if LIVE else "WALK PASSED"
    print(f"\n{prefix} -- {len(w.passed)} steps [{steps}] in {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
