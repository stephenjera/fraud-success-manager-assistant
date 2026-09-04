"""Endpoint tests for the P2 rule lifecycle (spec §7, the state machine).

Drives the frozen contract end to end: the catalog, the edit-and-own
``PATCH`` with its **freeze line** (clause sealed once a backtest row
exists → ``409 RULE_ILLEGAL_TRANSITION``), the deterministic backtest
(Gap C: ``labeled_only`` / ``full_universe`` / ``temporal_stability`` /
``sample``), and every legal/illegal FSM verb. LLM/reader faked
(``conftest``); Postgres + reference data are real.
"""

from __future__ import annotations

import re

from conftest import wait_until

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MISSING = "00000000-0000-0000-0000-000000000000"
PINS = "SELECT COUNT(*) FROM transactions WHERE amount_usd_cents > 100000"


def _draft(client) -> tuple[str, str]:
    """Pin + draft. Returns (insight_id, rule_id)."""
    cid = client.post("/v1/conversations").json()["conversation_id"]
    mid = client.post(
        f"/v1/conversations/{cid}/messages", json={"text": "How many large?"}
    ).json()["message_id"]
    wait_until(
        lambda: (
            client.get(f"/v1/conversations/{cid}/messages/{mid}").json()["status"]
            in ("success", "error")
        )
    )
    revision_id = client.get(f"/v1/conversations/{cid}/messages/{mid}").json()[
        "revisions"
    ][0]
    iid = client.post(
        f"/v1/conversations/{cid}/insights",
        json={"message_id": mid, "revision_id": revision_id, "sql": PINS},
    ).json()["insight_id"]
    return iid, client.post(f"/v1/insights/{iid}/draft-rule").json()["rule_id"]


class TestCatalog:
    def test_list_envelope_contains_rule(self, client, db_ok):
        iid, rid = _draft(client)
        env = client.get("/v1/rules").json()
        assert env["page"] == 1 and env["page_size"] and "token" in env
        hit = next(i for i in env["items"] if i["rule_id"] == rid)
        assert hit["status"] == "draft" and hit["source_insight_id"] == iid
        assert hit["backtests"] == 0 and hit["deployments"] == 0

    def test_list_filters_by_status(self, client, db_ok):
        iid, rid = _draft(client)
        items = [
            i["rule_id"]
            for i in client.get("/v1/rules", params={"status": "draft"}).json()["items"]
        ]
        assert rid in items
        assert rid not in [
            i["rule_id"]
            for i in client.get("/v1/rules", params={"status": "approved"}).json()[
                "items"
            ]
        ]

    def test_detail_shape(self, client, db_ok):
        iid, rid = _draft(client)
        body = client.get(f"/v1/rules/{rid}").json()
        assert body["rule_id"] == rid and body["status"] == "draft"
        assert body["provenance"]["source_insight_id"] == iid
        assert body["latest_backtest"] is None and body["deployment"] is None

    def test_detail_missing_is_404(self, client):
        r = client.get(f"/v1/rules/{MISSING}")
        assert r.status_code == 404 and r.json()["error"]["code"] == "STATE_NOT_FOUND"


class TestPatchFreezeLine:
    def test_title_always_editable(self, client, db_ok):
        _, rid = _draft(client)
        body = client.patch(f"/v1/rules/{rid}", json={"title": "Renamed"}).json()
        assert body["title"] == "Renamed" and body["status"] == "draft"

    def test_clause_editable_before_backtest(self, client, db_ok):
        _, rid = _draft(client)
        r = client.patch(
            f"/v1/rules/{rid}",
            json={"where_clause": "amount_usd_cents > 500000 AND transaction_type = 1"},
        )
        assert r.status_code == 200
        assert (
            client.get(f"/v1/rules/{rid}")
            .json()["where_clause"]
            .startswith("amount_usd_cents > 500000")
        )

    def test_bad_clause_is_sql_rejected(self, client, db_ok):
        _, rid = _draft(client)
        r = client.patch(
            f"/v1/rules/{rid}", json={"where_clause": "SELECT * FROM secrets"}
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "SQL_REJECTED"

    def test_clause_sealed_after_backtest_is_409(self, client, db_ok):
        _, rid = _draft(client)
        assert client.post(f"/v1/rules/{rid}/backtest").status_code == 201
        # The freeze line: clause sealed now, but the title stays open.
        r = client.patch(f"/v1/rules/{rid}", json={"where_clause": "amount > 1"})
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "RULE_ILLEGAL_TRANSITION"
        assert (
            client.patch(f"/v1/rules/{rid}", json={"title": "still ok"}).status_code
            == 200
        )


class TestBacktest:
    def test_dto_is_gap_c(self, client, db_ok):
        _, rid = _draft(client)
        r = client.post(f"/v1/rules/{rid}/backtest")
        assert r.status_code == 201
        body = r.json()
        for key in (
            "backtest_id",
            "labeled_only",
            "full_universe",
            "temporal_stability",
            "sample",
            "window",
        ):
            assert key in body, f"missing {key}"
        for block in (body["labeled_only"], body["full_universe"]):
            assert block["confusion_matrix"] and block["metrics"] and block["coverage"]
        # ADR-0014 invariants: full_universe scored every row; labeled_only a subset.
        assert (
            body["full_universe"]["coverage"]["total_rows"]
            >= body["labeled_only"]["coverage"]["total_rows"]
        )
        # The rule is now backtested (the row wrote the transition).
        assert client.get(f"/v1/rules/{rid}").json()["status"] == "backtested"

    def test_list_and_detail_round_trip(self, client, db_ok):
        _, rid = _draft(client)
        bid = client.post(f"/v1/rules/{rid}/backtest").json()["backtest_id"]
        items = client.get(f"/v1/rules/{rid}/backtests").json()["items"]
        assert any(i["backtest_id"] == bid for i in items)
        detail = client.get(f"/v1/rules/{rid}/backtests/{bid}").json()
        assert detail["backtest_id"] == bid
        # ADR-0014 temporal split: median-date earlier/later halves with real precision.
        ts = detail["temporal_stability"]
        assert "earlier_slice" in ts and "later_slice" in ts
        assert "precision" in ts["earlier_slice"] and "recall" in ts["earlier_slice"]
        assert "labeled_only" in detail and "full_universe" in detail


class TestApproveReject:
    def test_approve_from_backtested(self, client, db_ok):
        _, rid = _draft(client)
        client.post(f"/v1/rules/{rid}/backtest")
        r = client.post(
            f"/v1/rules/{rid}/approve",
            json={"rationale": "Lift is strong", "actor": "fsm-a"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "approved" and r.json()["approved_by"] == "fsm-a"

    def test_reject_from_backtested(self, client, db_ok):
        _, rid = _draft(client)
        client.post(f"/v1/rules/{rid}/backtest")
        r = client.post(
            f"/v1/rules/{rid}/reject", json={"rationale": "Too broad", "actor": "fsm-b"}
        )
        assert r.status_code == 200
        assert r.json()["status"] == "rejected" and r.json()["rationale"] == "Too broad"

    def test_approve_from_draft_is_409(self, client, db_ok):
        _, rid = _draft(client)
        r = client.post(
            f"/v1/rules/{rid}/approve",
            json={"rationale": "no backtest", "actor": "fsm"},
        )
        assert (
            r.status_code == 409
            and r.json()["error"]["code"] == "RULE_ILLEGAL_TRANSITION"
        )

    def test_reject_once_is_terminal(self, client, db_ok):
        _, rid = _draft(client)
        client.post(f"/v1/rules/{rid}/backtest")
        client.post(f"/v1/rules/{rid}/reject", json={"rationale": "x", "actor": "fsm"})
        # From ``rejected`` nothing is allowed — approve too.
        assert (
            client.post(
                f"/v1/rules/{rid}/approve", json={"rationale": "x", "actor": "fsm"}
            ).status_code
            == 409
        )


class TestDeploy:
    def test_deploy_end_to_end(self, client, db_ok):
        _, rid = _draft(client)
        client.post(f"/v1/rules/{rid}/backtest")
        client.post(
            f"/v1/rules/{rid}/approve", json={"rationale": "ok", "actor": "fsm"}
        )
        r = client.post(f"/v1/rules/{rid}/deploy")
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "deployed" and body["external_rule_id"].startswith(
            "mock-rule-"
        )
        assert body["backtest_id"] and body["deployment_id"]
        assert client.get(f"/v1/rules/{rid}").json()["status"] == "deployed"

    def test_deployment_status_reflects_deploy(self, client, db_ok):
        _, rid = _draft(client)
        assert client.get(f"/v1/rules/{rid}/deployment").json()["deployment"] is None
        client.post(f"/v1/rules/{rid}/backtest")
        client.post(
            f"/v1/rules/{rid}/approve", json={"rationale": "ok", "actor": "fsm"}
        )
        client.post(f"/v1/rules/{rid}/deploy")
        body = client.get(f"/v1/rules/{rid}/deployment").json()
        assert body["status"] == "deployed" and body["deployment"][
            "external_rule_id"
        ].startswith("mock-rule-")

    def test_disable_after_deploy(self, client, db_ok):
        _, rid = _draft(client)
        client.post(f"/v1/rules/{rid}/backtest")
        client.post(
            f"/v1/rules/{rid}/approve", json={"rationale": "ok", "actor": "fsm"}
        )
        client.post(f"/v1/rules/{rid}/deploy")
        r = client.post(f"/v1/rules/{rid}/disable")
        assert r.status_code == 200
        assert r.json()["status"] == "deployed" and r.json()["disabled_at"]
        assert client.get(f"/v1/rules/{rid}").json()["disabled_at"]

    def test_deploy_requires_approved(self, client, db_ok):
        """Deploy is legal only from ``approved`` — backtested / draft are 409."""
        _, rid = _draft(client)
        assert client.post(f"/v1/rules/{rid}/deploy").status_code == 409
        client.post(f"/v1/rules/{rid}/backtest")
        r = client.post(f"/v1/rules/{rid}/deploy")
        assert (
            r.status_code == 409
            and r.json()["error"]["code"] == "RULE_ILLEGAL_TRANSITION"
        )


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
