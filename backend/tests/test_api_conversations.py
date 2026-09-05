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
