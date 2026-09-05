# P6a — Backend error-contract fixes (implementation plan)

**Status:** planned, part of P6 (ADR-0017). Deps: P5 (done).
**Parent:** `P6-error-contract-and-frontend-redesign.md`
**Scope:** A1–A6 in the parent doc; fixes findings #3, #4, #11, #13 in
`../ux/fsm-evaluation-findings.md` (finding #5 is handled in P6b).

TDD, task-by-task, one commit per task. Backend only — no new dependencies,
`docs/ux/` untouched, no other phase or decision doc touched by this work.

## Goal

Make the API honest and safe: every error speaks one shape (`{"error": {code, message, details}}`), 500s carry CORS headers so the browser can actually read them, no exception internals ever reach the client, and the three correctness holes from the FSM evaluation (parse-error 500s, bad-UUID 500s, `is_fraud` leaking into rule clauses, unvalidated pinned SQL) are closed.

## Reference specs (read these first)

- `P6-error-contract-and-frontend-redesign.md` — scope A1–A6, DoD.
- `../ux/fsm-evaluation-findings.md` — findings #3, #4, #5, #11, #13 (this plan fixes #3, #4, #11, #13; #5 is P6b).
- `../decisions/0017-p6-redesign-scope.md` — ADR.

## Architecture / Tech stack

FastAPI + psycopg + sqlglot (all existing dependencies — **no new packages**). Fix sites: `app/api/errors.py` (500 handler), `app/core/sql_validator.py` (parse guard), `app/services/store.py` + `app/services/rules.py` (uuid guards), `app/core/rules.py` (label gate), `app/services/rules.py` (pin SQL validation, draft-rule 400). Tests: `pytest` under `backend/tests/`; pure-logic tests are `unittest.TestCase`, API tests use the `client` + `db_ok` fixtures from `conftest.py`.

## Global constraints

- **TDD, no exceptions:** every task starts with a failing test, run to see it fail, then the minimal fix, then green. One commit per task, message `fix(backend): <what>`.
- Error envelope is frozen: `{"error": {"code": <code>, "message": <str>, "details": <object|null>}}`. No new error codes — reuse `INTERNAL_ERROR`, `STATE_NOT_FOUND`, `SQL_REJECTED`.
- 500 responses: `details` is always `null`. 4xx `details` may carry user-supplied values (e.g. `offending_sql`) — never exception text, never DB internals.
- `docs/ux/*` stays **untracked** — never `git add` it.
- `git commit` always includes the trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>` (blank line before it).
- Run from `backend/`: `uv run pytest tests -q`. DB-backed tests skip automatically without Postgres (`db_ok` fixture).
- Do not break any currently-passing test. After each task, the FULL suite is green.

## Verified current behavior (baseline, do not re-derive)

- `POST /v1/conversations/not-a-uuid/messages` → **500**, `details.error = "invalid input syntax for type uuid: 'x'"`, and **no** `access-control-allow-origin` header (both confirmed live via TestClient).
- `validate_sql("(((")` and `validate_sql("x = ")` → sqlglot `ParseError` **escapes** → 500 (confirmed). `validate_sql("THIS IS NOT SQL")` → already `SqlRejected`.
- `validate_sql("SELECT * FROM transactionz")` → currently **admitted** (validator doesn't know table names). Out of scope.
- `derive_where_clause` returns the pinned SQL's WHERE condition verbatim (incl. `is_fraud` columns) — so a label clause reaches `draft_rule` via derivation even after the pin-time gate.
- The `Exception` handler runs under `ServerErrorMiddleware`, **outside** CORSMiddleware; 4xx handlers run inside it. Only the 500 path needs self-attached CORS headers; 4xx must keep exactly one ACAO header.

## Files

| File | Change |
|---|---|
| `backend/app/api/errors.py` | T1: CORS headers on 500, `details: null` |
| `backend/app/core/sql_validator.py` | T2: `ParseError` → `SqlRejected` |
| `backend/app/services/store.py` | T3: `is_uuid` guard on uuid lookups |
| `backend/app/services/rules.py` | T3: uuid guards; T5: `draft_rule` 400; T6: pin/patch SQL validation |
| `backend/app/core/rules.py` | T4: `is_fraud` label gate |
| `backend/tests/test_errors.py` (new) | T1 |
| `backend/tests/test_sql_validator.py` | T2 |
| `backend/tests/test_api_conversations.py` (new) | T3 |
| `backend/tests/test_rules_label_gate.py` (new) | T4 |
| `backend/tests/test_api_rules.py` | T5 |
| `backend/tests/test_api_insights.py` | T6 |

## Task 1 — 500 responses carry CORS and leak nothing (findings #4 + #3 leak, A1)

**Files:** `backend/tests/test_errors.py` (new), `backend/app/api/errors.py`

**Interfaces:** `_cors_headers(request) -> dict[str, str]` (module-private); `_internal` handler signature changes to `(request: Request, exc: Exception)`.

1. Create `backend/tests/test_errors.py`:

```python
"""A1: 500s carry CORS for allowed origins and never leak exception internals.

The Exception handler runs under ServerErrorMiddleware (outside the CORS
middleware stack), so the handler itself must attach CORS headers — and must
not echo exception text into ``details`` (findings #3/#4).
"""

import warnings

warnings.filterwarnings("ignore", message=".*uvloop.*")

import pytest
from fastapi.testclient import TestClient

from app.common.settings import Settings
from app.main import create_app

ALLOWED = "http://localhost:5173"


@pytest.fixture()
def cors_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        Settings, "cors_origins", property(lambda self: [ALLOWED])
    )
    app = create_app()

    @app.post("/boom")
    def boom() -> None:
        raise RuntimeError("psycopg internal boom detail")

    return TestClient(app, base_url=ALLOWED, raise_server_exceptions=False)


def test_500_has_cors_for_allowed_origin(cors_client: TestClient) -> None:
    r = cors_client.post("/boom", headers={"origin": ALLOWED})
    assert r.status_code == 500
    assert r.headers["access-control-allow-origin"] == ALLOWED
    assert r.headers["access-control-allow-credentials"] == "true"


def test_500_no_cors_for_disallowed_origin(cors_client: TestClient) -> None:
    r = cors_client.post("/boom", headers={"origin": "http://evil.example"})
    assert r.status_code == 500
    assert "access-control-allow-origin" not in r.headers


def test_500_body_never_leaks_details(cors_client: TestClient) -> None:
    r = cors_client.post("/boom")
    body = r.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["error"]["message"] == "Unexpected server error."
    assert body["error"]["details"] is None
    assert "boom detail" not in r.text
    assert "psycopg" not in r.text


def test_404_still_has_single_cors_header(cors_client: TestClient) -> None:
    r = cors_client.get("/no-such-route", headers={"origin": ALLOWED})
    assert r.status_code == 404
    assert r.headers.get_list("access-control-allow-origin") == [ALLOWED]


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
```

2. Run `cd backend && uv run pytest tests/test_errors.py -q` → **expect FAIL** (no ACAO header on 500; body leaks `details.error`).
3. In `backend/app/api/errors.py`: add import `from app.common.settings import settings`; replace the `_internal` handler with:

```python
def _cors_headers(request: Request) -> dict[str, str]:
    """CORS for a response the middleware stack will not see (ServerErrorMiddleware)."""
    origin = request.headers.get("origin")
    if origin in settings.cors_origins:
        return {
            "access-control-allow-origin": origin,
            "access-control-allow-credentials": "true",
        }
    return {}


@app.exception_handler(Exception)
async def _internal(request: Request, exc: Exception) -> JSONResponse:
    """500 envelope: generic message, no exception text (leak), self-attached CORS."""
    return JSONResponse(
        status_code=500,
        content=ApiError(INTERNAL_ERROR, "Unexpected server error.").body(),
        headers=_cors_headers(request),
    )
```

   (Keep any log line the existing handler has; the rest of the handler body is replaced.)
4. Run `uv run pytest tests/test_errors.py -q` → **expect 4 passed**.
5. Run the full suite `uv run pytest tests -q` → green.
6. Commit: `fix(backend): 500s carry CORS headers and never leak exception details`

## Task 2 — unparseable SQL is a 400, not a 500 (finding #3, A2)

**Files:** `backend/tests/test_sql_validator.py`, `backend/app/core/sql_validator.py`

1. Add to `test_sql_validator.py` (unittest style):

```python
class ParseErrorIsRejected(unittest.TestCase):
    """sqlglot ParseError must surface as SqlRejected, never escape (A2)."""

    def _assert_rejected(self, sql: str) -> None:
        with self.assertRaises(SqlRejected) as ctx:
            validate_sql(sql)
        self.assertTrue(ctx.exception.reason)
        self.assertEqual(ctx.exception.sql, sql)

    def test_unbalanced_parens_rejected(self) -> None:
        self._assert_rejected("(((")

    def test_dangling_expression_rejected(self) -> None:
        self._assert_rejected("x =")

    def test_garbage_still_rejected(self) -> None:
        self._assert_rejected("THIS IS NOT SQL")
```

2. Run `uv run pytest tests/test_sql_validator.py -q` → **expect 2 failed** (ParseError escapes), 1 passed.
3. In `sql_validator.py` `validate_sql`, replace the bare parse:

```python
    try:
        parsed = sqlglot.parse(text, read=_DIALECT)
    except sqlglot.errors.ParseError as exc:
        raise SqlRejected("Could not parse as SQL.", text) from exc
```

4. Run → all passed. 5. Full suite → green.
6. Commit: `fix(backend): reject unparseable SQL with 400 SQL_REJECTED instead of 500`

## Task 3 — bad-UUID path params are 404, not 500 (finding #3, A3)

**Files:** `backend/tests/test_api_conversations.py` (new), `backend/app/services/store.py`, `backend/app/services/rules.py`

**Interfaces:** `store.is_uuid(value: str) -> bool` (new, public). `get_conversation` returns `None` for non-uuids; `get_message` raises `store.NotFound` for non-uuids.

1. Create `backend/tests/test_api_conversations.py`:

```python
"""A3: uuid path params that are not uuids are 404 STATE_NOT_FOUND, never 500."""

import warnings

warnings.filterwarnings("ignore", message=".*uvloop.*")

import pytest
from fastapi.testclient import TestClient

MISSING = "00000000-0000-0000-0000-000000000000"


def test_get_conversation_bad_uuid_is_404(client: TestClient, db_ok: None) -> None:
    r = client.get("/v1/conversations/not-a-uuid")
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "STATE_NOT_FOUND"


def test_get_conversation_missing_uuid_is_404(client: TestClient, db_ok: None) -> None:
    r = client.get(f"/v1/conversations/{MISSING}")
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "STATE_NOT_FOUND"


def test_get_message_bad_uuids_are_404(client: TestClient, db_ok: None) -> None:
    r = client.get(f"/v1/conversations/{MISSING}/messages/{MISSING}")
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "STATE_NOT_FOUND"


def test_list_conversations_is_200(client: TestClient, db_ok: None) -> None:
    r = client.get("/v1/conversations")
    assert r.status_code == 200, r.text
    # envelope (ADR-0011, api-contract.md): {items, page, page_size, token}
    assert "items" in r.json()


def test_get_rule_bad_uuid_is_404(client: TestClient, db_ok: None) -> None:
    r = client.get("/v1/rules/not-a-uuid")
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "STATE_NOT_FOUND"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
```

2. Run → expect FAIL pre-fix (skipped without DB).
3. In `store.py`:

```python
def is_uuid(value: str) -> bool:
    """True when ``value`` is a syntactically valid uuid (path-param guard, A3)."""
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True
```

   In `get_conversation`, first line of body: `if not is_uuid(conversation_id): return None`
   In `get_message`, first lines of body: `if not is_uuid(conversation_id) or not is_uuid(message_id): raise NotFound(f"{message_id!r} not found")`
4. In `services/rules.py`:
   - `_get_rule(rule_id)`: first line `if not store.is_uuid(rule_id): raise api_errors.not_found(f"Rule {rule_id!r} not found.")`
   - `draft_rule(insight_id, ...)`: same guard for `insight_id` (`f"Insight {insight_id!r} not found."`).
   - `get_insight`/`patch_insight`/`delete_insight`: same guard where path ids hit `_con().execute` without first going through `store.get_message`.
5. Run → passed. 6. Full suite green.
7. Commit: `fix(backend): bad-uuid path params return 404 STATE_NOT_FOUND instead of 500`

## Task 4 — rule clauses may not reference the fraud label (finding #13, A4)

**Files:** `backend/tests/test_rules_label_gate.py` (new), `backend/app/core/rules.py`

1. Create `backend/tests/test_rules_label_gate.py`:

```python
"""A4: a rule clause must never reference the fraud label (finding #13)."""

import unittest
import warnings

warnings.filterwarnings("ignore", message=".*uvloop.*")

from app.core import rules


class LabelGateTests(unittest.TestCase):
    def test_label_only_clause_rejected(self) -> None:
        with self.assertRaises(rules.InvalidWhereClause):
            rules.validate_where_clause("fl.is_fraud = 1")

    def test_label_and_behavior_clause_rejected(self) -> None:
        with self.assertRaises(rules.InvalidWhereClause):
            rules.validate_where_clause(
                "fl.is_fraud = 1 AND amount_usd_cents > 100000"
            )

    def test_plain_behavior_clause_still_allowed(self) -> None:
        clause = rules.validate_where_clause("amount_usd_cents > 100000")
        assert "amount_usd_cents" in clause

    def test_gate_error_names_the_column(self) -> None:
        with self.assertRaises(rules.InvalidWhereClause) as ctx:
            rules.validate_where_clause("fl.is_fraud = 1")
        self.assertIn("is_fraud", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

2. Run → expect 2 failed, 2 passed.
3. In `core/rules.py`: near `_ALLOWED_TABLES`: `_LABEL_COLUMNS = frozenset({"is_fraud"})`. In `validate_where_clause`, after the table-basis loop, before `return`:

```python
    if {c.name.lower() for c in cond.find_all(exp.Column)} & _LABEL_COLUMNS:
        raise InvalidWhereClause(
            "Rule clauses must not reference the fraud label (is_fraud); "
            "rules must be based on behavioral signals only."
        )
```

4. Run → 4 passed. 5. Full suite green.
6. Commit: `fix(backend): reject rule clauses that reference the fraud label (is_fraud)`

## Task 5 — draft-rule with an invalid clause is a 400, not a 500 (finding #13, A5)

**Files:** `backend/tests/test_api_rules.py`, `backend/app/services/rules.py`

1. Append to `test_api_rules.py` (reuse existing `client`/`db_ok` fixtures and `wait_until`):

```python
class TestDraftInvalidClause400:
    """A derived clause that trips the label gate is a 400, not a 500 (A5)."""

    def test_derived_label_clause_is_sql_rejected(
        self, client: TestClient, db_ok: None
    ) -> None:
        cid = client.post("/v1/conversations").json()["conversation_id"]
        msg = client.post(
            f"/v1/conversations/{cid}/messages",
            json={"text": "How many large flagged ones?"},
        ).json()
        wait_until(
            lambda: client.get(
                f"/v1/conversations/{cid}/messages/{msg['message_id']}"
            ).json()["status"]
            in ("success", "error")
        )
        m = client.get(
            f"/v1/conversations/{cid}/messages/{msg['message_id']}"
        ).json()
        revision_id = m["revisions"][0]
        pin = client.post(
            f"/v1/conversations/{cid}/insights",
            json={
                "message_id": msg["message_id"],
                "revision_id": revision_id,
                "sql": (
                    "SELECT COUNT(*) FROM transactions t "
                    "WHERE t.amount_usd_cents > 100000 AND t.is_fraud = 1"
                ),
            },
        )
        assert pin.status_code == 201, pin.text
        insight_id = pin.json()["insight_id"]
        r = client.post(f"/v1/insights/{insight_id}/draft-rule")
        assert r.status_code == 400, r.text
        err = r.json()["error"]
        assert err["code"] == "SQL_REJECTED"
        assert "is_fraud" in str(err.get("details"))
        # A5 gate: the clause failed validation before INSERT — no rule row.
        rules = client.get("/v1/rules").json()["items"]
        assert all(row.get("source_insight_id") != insight_id for row in rules)
```

   (The pin succeeds — SQL is legal — gate fires at draft time via `derive_where_clause` verbatim pass-through.)

2. Run → expect FAIL (currently 500).
3. In `services/rules.py` `draft_rule`, wrap clause validation:

```python
    try:
        if ins[2]:
            where = core_rules.validate_where_clause(ins[2])
        else:
            where = core_rules.derive_where_clause(ins[1])
        canonical = core_rules.validate_where_clause(where)
    except core_rules.InvalidWhereClause as exc:
        raise api_errors.ApiError(
            api_errors.SQL_REJECTED,
            str(exc),
            details={"offending_clause": where},
        ) from exc
```

   (Mirror `patch_rule`'s existing catch shape; no new error shape.)
4. Run `test_api_rules.py` → all passed. 5. Full suite green.
6. Commit: `fix(backend): draft-rule with an invalid clause returns 400 SQL_REJECTED`

## Task 6 — pin/patch must validate SQL (finding #11, A6)

**Files:** `backend/tests/test_api_insights.py`, `backend/app/services/rules.py`

1. Append to `test_api_insights.py`:

```python
def _make_pinned_message(client: TestClient) -> tuple[str, dict, str]:
    cid = client.post("/v1/conversations").json()["conversation_id"]
    msg = client.post(
        f"/v1/conversations/{cid}/messages",
        json={"text": "How many large?"},
    ).json()
    wait_until(
        lambda: client.get(
            f"/v1/conversations/{cid}/messages/{msg['message_id']}"
        ).json()["status"]
        in ("success", "error")
    )
    m = client.get(
        f"/v1/conversations/{cid}/messages/{msg['message_id']}"
    ).json()
    return cid, m, m["revisions"][0]


class TestPinSqlValidation:
    """Pinned SQL is validated: garbage is a 400 SQL_REJECTED, not a 201 (A5)."""

    def test_pin_rejects_garbage_sql(self, client: TestClient, db_ok: None) -> None:
        cid, msg, revision_id = _make_pinned_message(client)
        r = client.post(
            f"/v1/conversations/{cid}/insights",
            json={
                "message_id": msg["message_id"],
                "revision_id": revision_id,
                "sql": "THIS IS NOT SQL",
            },
        )
        assert r.status_code == 400, r.text
        err = r.json()["error"]
        assert err["code"] == "SQL_REJECTED"
        assert err["details"]["offending_sql"] == "THIS IS NOT SQL"

    def test_pin_rejects_unparseable_sql(self, client: TestClient, db_ok: None) -> None:
        cid, msg, revision_id = _make_pinned_message(client)
        r = client.post(
            f"/v1/conversations/{cid}/insights",
            json={
                "message_id": msg["message_id"],
                "revision_id": revision_id,
                "sql": "(((",
            },
        )
        assert r.status_code == 400, r.text
        assert r.json()["error"]["details"]["offending_sql"] == "(((")
```

   (Adopt file's existing fixture/import style; `revisions` entries are plain revision-id **strings**.)

2. Run `-k TestPinSqlValidation` → expect FAIL (both currently 201).
3. In `services/rules.py`: ensure `from app.core import sql_validator` imported. In `pin_insight`, before INSERT:

```python
    try:
        sql_validator.validate_sql(sql)
    except sql_validator.SqlRejected as exc:
        raise api_errors.sql_rejected(exc.reason, exc.sql) from exc
```

   Same guard in `patch_insight` when `sql is not None`, before UPDATE.
4. Run `test_api_insights.py` → all passed. 5. Full suite green.
6. Commit: `fix(backend): validate pinned and patched SQL; reject garbage with 400 SQL_REJECTED`

## Task 7 — finding #5 ("Unnamed rule" titles) is already handled — verify and document

1. Verified: `draft_rule` computes `chosen_title = title or ins[3] or "Unnamed rule"`; `POST /v1/insights/{id}/draft-rule` accepts `{"title": "..."}` — the backend **already supports** titles (P5 stored `rule_title` on the insight; `draft_rule` prefers it). "Unnamed rule" rows in the seed come from the draft path with no model-proposed title; the string only appears in one place (`services/rules.py:303`), no seed SQL contains it.
2. No code change. The UI displays whatever the API returns (P6b B6 clause editor shows the title); there is no frontend "Unnamed rule" fallback (grep-verified).
3. No commit.

## Final verification (after all tasks)

1. `cd backend && uv run pytest tests -q` → all green.
2. Smoke: bad-uuid GET with Origin → 404 + single ACAO; a 500 with Origin → ACAO + `details: null`; pin garbage SQL → 400 `SQL_REJECTED`.
3. `git status` → `docs/ux/*` untracked.
4. Update phase-doc DoD checkboxes as tasks land.

## Definition of done (P6a)

- Findings #3, #4, #11, #13 no longer reproduce (each has a regression test).
- No 500 for bad input; input errors are 400/404 with the frozen envelope.
- 500s CORS-safe, leak nothing.
- Full suite green; no new dependencies; `docs/ux/*` untracked.