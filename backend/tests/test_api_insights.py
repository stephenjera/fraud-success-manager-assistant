"""Endpoint tests for the P2 insight routes (the pin → draft bridge).

Covers the frozen contract: the Gap-B pin (``revision_id`` + ``sql`` are the
proof the client saw a query), the insight rail, and ``draft-rule`` (a rule
only ever originates from a pinned insight — principle 5, enforced by the FK,
not by a prompt). LLM/reader faked (``conftest``); Postgres + store real.
"""

from __future__ import annotations

import re

from conftest import wait_until

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MISSING = "00000000-0000-0000-0000-000000000000"

# A pinned query with an explicit filter, so the derived clause is real (not ``1=1``).
PINS = "SELECT COUNT(*) FROM transactions WHERE amount_usd_cents > 100000"


def _pin_client(client) -> tuple[str, str, str]:
    """Drive the explore loop to a grounded message and pin it. Returns (cid, mid, revision_id)."""
    cid = client.post("/v1/conversations").json()["conversation_id"]
    mid = client.post(
        f"/v1/conversations/{cid}/messages",
        json={"text": "How many large transactions?"},
    ).json()["message_id"]
    wait_until(
        lambda: (
            client.get(f"/v1/conversations/{cid}/messages/{mid}").json()["status"]
            in ("success", "error")
        )
    )
    detail = client.get(f"/v1/conversations/{cid}/messages/{mid}").json()
    revision_id = detail["revisions"][
        0
    ]  # the message detail lists revision ids (strings)
    return cid, mid, revision_id


def _pin(client) -> tuple[str, str]:
    """Pin the first grounded revision. Returns (cid, insight_id)."""
    cid, mid, revision_id = _pin_client(client)
    r = client.post(
        f"/v1/conversations/{cid}/insights",
        json={
            "message_id": mid,
            "revision_id": revision_id,
            "sql": PINS,
            "explanation": "Large-card spend.",
        },
    )
    assert r.status_code == 201, r.text
    return cid, r.json()["insight_id"]


class TestPin:
    def test_pin_returns_gap_b_dto(self, client, db_ok):
        cid, mid, revision_id = _pin_client(client)
        r = client.post(
            f"/v1/conversations/{cid}/insights",
            json={"message_id": mid, "revision_id": revision_id, "sql": PINS},
        )
        assert r.status_code == 201
        body = r.json()
        assert UUID_RE.match(body["insight_id"])
        assert body["message_id"] == mid and body["revision_id"] == revision_id
        assert body["sql"] == PINS and body["created_at"]

    def test_pin_appears_in_rail(self, client, db_ok):
        cid, iid = _pin(client)
        items = client.get(f"/v1/conversations/{cid}/insights").json()["items"]
        assert any(item["insight_id"] == iid for item in items)

    def test_pin_missing_revision_is_state_not_found(self, client, db_ok):
        cid, mid, _ = _pin_client(client)
        r = client.post(
            f"/v1/conversations/{cid}/insights",
            json={"message_id": mid, "revision_id": MISSING, "sql": PINS},
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "STATE_NOT_FOUND"

    def test_pin_missing_conversation_is_404(self, client):
        r = client.post(
            f"/v1/conversations/{MISSING}/insights",
            json={"message_id": MISSING, "revision_id": MISSING, "sql": PINS},
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "STATE_NOT_FOUND"


class TestInsightCrud:
    def test_get_full_detail(self, client, db_ok):
        cid, iid = _pin(client)
        body = client.get(f"/v1/insights/{iid}").json()
        assert body["insight_id"] == iid
        assert body["sql"] == PINS
        assert body["revisions"] and body["rule_count"] == 0

    def test_get_missing_is_404(self, client):
        r = client.get(f"/v1/insights/{MISSING}")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "STATE_NOT_FOUND"

    def test_patch_edits_sql_and_explanation(self, client, db_ok):
        _, iid = _pin(client)
        new_sql = "SELECT COUNT(*) FROM transactions WHERE amount > 5000"
        r = client.patch(
            f"/v1/insights/{iid}", json={"sql": new_sql, "explanation": "Bigger cards."}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["sql"] == new_sql and body["explanation"] == "Bigger cards."

    def test_delete_cascades(self, client, db_ok):
        _, iid = _pin(client)
        assert client.delete(f"/v1/insights/{iid}").status_code == 204
        assert client.get(f"/v1/insights/{iid}").status_code == 404


class TestDraftRule:
    def test_draft_rule_from_insight(self, client, db_ok):
        _, iid = _pin(client)
        r = client.post(f"/v1/insights/{iid}/draft-rule", json={"title": "Big cards"})
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "draft"
        # PINS has ``amount_usd_cents > 100000`` as its only filter, so that is the clause.
        assert body["where_clause"] == "amount_usd_cents > 100000"
        assert body["source_insight_id"] == iid
        assert "rationale" in body and "assumptions" in body
        assert body["created_at"]

    def test_draft_rule_missing_insight_is_404(self, client):
        r = client.post(f"/v1/insights/{MISSING}/draft-rule")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "STATE_NOT_FOUND"


class TestPinSqlValidation:
    """Pinned/patched SQL is validated: garbage is a 400 SQL_REJECTED, not a 201 (A6)."""

    def test_pin_rejects_garbage_sql(self, client, db_ok):
        cid, mid, revision_id = _pin_client(client)
        body = {"message_id": mid, "revision_id": revision_id, "sql": "THIS IS NOT SQL"}
        r = client.post(f"/v1/conversations/{cid}/insights", json=body)
        assert r.status_code == 400, r.text
        err = r.json()["error"]
        assert err["code"] == "SQL_REJECTED"
        assert err["details"]["offending_sql"] == "THIS IS NOT SQL"

    def test_pin_rejects_unparseable_sql(self, client, db_ok):
        cid, mid, revision_id = _pin_client(client)
        body = {"message_id": mid, "revision_id": revision_id, "sql": "((("}
        r = client.post(f"/v1/conversations/{cid}/insights", json=body)
        assert r.status_code == 400, r.text
        assert r.json()["error"]["details"]["offending_sql"] == "((("

    def test_patch_rejects_unparseable_sql(self, client, db_ok):
        _, iid = _pin(client)
        r = client.patch(f"/v1/insights/{iid}", json={"sql": "((("})
        assert r.status_code == 400, r.text
        assert r.json()["error"]["details"]["offending_sql"] == "((("
