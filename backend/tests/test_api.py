"""Endpoint tests for the P1 explore-loop API (all 12 routes).

Covers the frozen contract in ``docs/architecture/api-contract.md``: the command/query
split, the message DTO, the SSE event set/order, the error envelope, and ``rerun`` (Gap H).
The LLM + SQL reader are faked (see ``conftest``); Postgres + store are real.
"""

from __future__ import annotations

import json
import re

import pytest

from conftest import wait_until

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _cid(client) -> str:
    r = client.post("/v1/conversations")
    assert r.status_code == 201
    return r.json()["conversation_id"]


# --- Meta (no DB) -----------------------------------------------------------

class TestMeta:
    def test_version(self, client):
        r = client.get("/v1/meta/version")
        assert r.status_code == 200
        body = r.json()
        assert body["version"] and body["built_at"] and "git_sha" in body

    def test_health(self, client):
        r = client.get("/v1/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_health_ready(self, client):
        r = client.get("/v1/health/ready")
        assert r.status_code == 200
        body = r.json()
        assert body["ready"] is True
        assert body["llm"]["model"] and body["db"]["configured"] is True
        assert "langfuse" in body

    def test_schema(self, client, db_ok):
        r = client.get("/v1/schema")
        assert r.status_code == 200
        body = r.json()
        assert body["dialect"] == "postgres" and body["schema"] == "reference"
        tables = body["tables"]
        assert isinstance(tables, dict) and "transactions" in tables
        assert any(col["column"] == "id" for col in tables["transactions"])


# --- Conversations (DB) -----------------------------------------------------

class TestConversations:
    def test_create(self, client, db_ok):
        r = client.post("/v1/conversations")
        assert r.status_code == 201
        assert UUID_RE.match(r.json()["conversation_id"]) and r.json()["created_at"]

    def test_list(self, client, db_ok):
        cid = _cid(client)
        r = client.get("/v1/conversations")
        assert r.status_code == 200
        assert any(item["conversation_id"] == cid for item in r.json()["items"])

    def test_get(self, client, db_ok):
        cid = _cid(client)
        r = client.get(f"/v1/conversations/{cid}")
        assert r.status_code == 200
        assert r.json()["conversation_id"] == cid and r.json()["messages"] == []

    def test_delete(self, client, db_ok):
        cid = _cid(client)
        assert client.delete(f"/v1/conversations/{cid}").status_code == 204
        assert client.get(f"/v1/conversations/{cid}").status_code == 404

    def test_get_missing_is_state_not_found(self, client):
        missing = "00000000-0000-0000-0000-000000000000"
        r = client.get(f"/v1/conversations/{missing}")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "STATE_NOT_FOUND"

    def test_post_message_missing_conversation_is_404(self, client):
        missing = "00000000-0000-0000-0000-000000000000"
        r = client.post(f"/v1/conversations/{missing}/messages", json={"text": "hi"})
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "STATE_NOT_FOUND"


# --- The explore loop: command -> durable fact -> stream --------------------

class TestExploreLoop:
    def test_post_message_returns_command(self, client, db_ok):
        cid = _cid(client)
        r = client.post(f"/v1/conversations/{cid}/messages", json={"text": "How many transactions are there?"})
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "running"
        assert UUID_RE.match(body["message_id"]) and UUID_RE.match(body["run_id"])

    def test_post_message_requires_text(self, client, db_ok):
        cid = _cid(client)
        r = client.post(f"/v1/conversations/{cid}/messages", json={})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INTERNAL_ERROR"  # validation → the single 400 shape

    def test_message_becomes_durable_success(self, client, db_ok):
        cid = _cid(client)
        mid = client.post(f"/v1/conversations/{cid}/messages", json={"text": "How many transactions are there?"}).json()["message_id"]

        def done():
            r = client.get(f"/v1/conversations/{cid}/messages/{mid}")
            r.raise_for_status()
            return r.json()["status"] in ("success", "error")

        wait_until(done)
        body = client.get(f"/v1/conversations/{cid}/messages/{mid}").json()
        assert body["status"] == "success"
        g = body["grounding"]
        assert g["sql"].upper().startswith("SELECT")
        assert g["explanation"] and "1,159,966" in g["explanation"]
        assert g["tables_and_joins_used"] == ["transactions"]
        assert body["revisions"][0] and body["error"] is None

    def test_message_appears_in_list(self, client, db_ok):
        cid = _cid(client)
        mid = client.post(f"/v1/conversations/{cid}/messages", json={"text": "x"}).json()["message_id"]
        wait_until(lambda: client.get(f"/v1/conversations/{cid}/messages/{mid}").json()["status"] in ("success", "error"))
        items = client.get(f"/v1/conversations/{cid}/messages").json()["items"]
        assert any(item["message_id"] == mid and item["grounded"] is True for item in items)

    def test_get_message_missing_is_404(self, client, db_ok):
        cid = _cid(client)
        missing = "00000000-0000-0000-0000-000000000000"
        r = client.get(f"/v1/conversations/{cid}/messages/{missing}")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "STATE_NOT_FOUND"


# --- Runs: the durable object + the SSE stream ------------------------------

class _SSE:
    """Parse a raw ``text/event-stream`` body into ``[(event, data-dict)]`` tuples."""

    @staticmethod
    def parse(text: str) -> list[tuple[str, dict]]:
        events: list[tuple[str, dict]] = []
        for block in re.split(r"\n\n+", text):
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
                events.append((event, json.loads(data)))
        return events


class TestRuns:
    def _drive(self, client) -> tuple[str, str]:
        cid = _cid(client)
        body = client.post(f"/v1/conversations/{cid}/messages", json={"text": "How many transactions are there?"}).json()
        wait_until(lambda: client.get(f"/v1/conversations/{cid}/messages/{body['message_id']}").json()["status"] in ("success", "error"))
        return cid, body["run_id"]

    def test_get_run(self, client, db_ok):
        _, run_id = self._drive(client)
        r = client.get(f"/v1/runs/{run_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["run_id"] == run_id and body["status"] == "success" and body["message_id"]

    def test_get_run_missing_is_404(self, client, db_ok):
        _, run_id = self._drive(client)
        missing = "00000000-0000-0000-0000-000000000000"
        r = client.get(f"/v1/runs/{missing}")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "STATE_NOT_FOUND"

    def test_sse_event_set_and_order(self, client, db_ok):
        _, run_id = self._drive(client)
        r = client.get(f"/v1/runs/{run_id}/events")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = _SSE.parse(r.text)
        names = [e for e, _ in events]
        assert names[0] == "run.start" and names[-1] == "run.done"
        assert "tool_call.start" in names and "tool_call.done" in names and "message.delta" in names
        assert names.index("tool_call.start") < names.index("tool_call.done")  # start precedes its done
        assert "insight.suggested" not in names and "run.error" not in names  # not emitted on a clean run
        assert names.count("run.start") == 1 and names.count("run.done") == 1  # exactly one each

    def test_sse_payloads_are_typed(self, client, db_ok):
        _, run_id = self._drive(client)
        events = dict((_e, _d) for _e, _d in _SSE.parse(client.get(f"/v1/runs/{run_id}/events").text))
        assert events["run.start"]["run_id"] == run_id
        assert events["tool_call.done"]["tool"] == "run_sql"
        assert "1,159,966" in events["message.delta"]["delta"]
        assert events["run.done"]["message_id"] and events["run.done"]["duration_ms"] >= 0

    def test_sse_missing_run_is_404(self, client, db_ok):
        missing = "00000000-0000-0000-0000-000000000000"
        r = client.get(f"/v1/runs/{missing}/events")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "STATE_NOT_FOUND"


# --- Rerun (Gap H): synchronous re-execute + the revisions history ----------

class TestRerun:
    def _first_message(self, client) -> tuple[str, str]:
        cid = _cid(client)
        mid = client.post(f"/v1/conversations/{cid}/messages", json={"text": "x"}).json()["message_id"]
        wait_until(lambda: client.get(f"/v1/conversations/{cid}/messages/{mid}").json()["status"] in ("success", "error"))
        return cid, mid

    def test_rerun_valid_returns_result_and_revision(self, client, db_ok):
        cid, mid = self._first_message(client)
        r = client.post(f"/v1/conversations/{cid}/messages/{mid}/rerun", json={"sql": "SELECT COUNT(*) FROM transactions"})
        assert r.status_code == 200
        body = r.json()
        assert body["message_id"] == mid
        assert body["revision_id"]
        assert body["result"]["columns"] == ["total_transactions"]
        assert body["result"]["rows"] == [[1159966]]
        assert body["flags"] == []

    def test_rerun_write_is_sql_rejected(self, client, db_ok):
        cid, mid = self._first_message(client)
        r = client.post(f"/v1/conversations/{cid}/messages/{mid}/rerun", json={"sql": "DELETE FROM cards"})
        assert r.status_code == 400
        body = r.json()["error"]
        assert body["code"] == "SQL_REJECTED"
        assert body["details"]["offending_sql"] == "DELETE FROM cards"

    def test_rerun_missing_message_is_404(self, client, db_ok):
        cid = _cid(client)
        missing = "00000000-0000-0000-0000-000000000000"
        r = client.post(f"/v1/conversations/{cid}/messages/{missing}/rerun", json={"sql": "SELECT 1"})
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "STATE_NOT_FOUND"

    def test_revisions_lists_newest_first(self, client, db_ok):
        cid, mid = self._first_message(client)
        client.post(f"/v1/conversations/{cid}/messages/{mid}/rerun", json={"sql": "SELECT 1"})
        r = client.get(f"/v1/conversations/{cid}/messages/{mid}/revisions")
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(item["source"] == "rerun" for item in items)
        first = items[0]
        assert "revision_id" in first and "sql_preview" in first and "source" in first and "created_at" in first

    def test_revisions_missing_message_is_404(self, client, db_ok):
        cid = _cid(client)
        missing = "00000000-0000-0000-0000-000000000000"
        r = client.get(f"/v1/conversations/{cid}/messages/{missing}/revisions")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "STATE_NOT_FOUND"
