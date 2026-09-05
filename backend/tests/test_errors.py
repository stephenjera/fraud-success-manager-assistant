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
