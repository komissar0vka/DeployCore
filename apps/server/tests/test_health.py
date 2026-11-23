import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from deploycore import health, main


@pytest.fixture
def client(monkeypatch):
    for key in ("HOST", "DB", "USER", "PASSWORD"):
        monkeypatch.setenv(f"POSTGRES_{key}", "unused")
    with TestClient(main.app) as test_client:
        yield test_client


def test_database_ready(client, monkeypatch):
    checked = []
    monkeypatch.setattr(health, "check_database", checked.append)
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"
    assert checked == [main.app.state.database]


def test_database_failure_does_not_affect_liveness(client, monkeypatch):
    def unavailable(engine):
        raise OperationalError(None, None, Exception("private DSN"))

    monkeypatch.setattr(health, "check_database", unavailable)
    response = client.get("/api/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/api/health/live").json() == {"status": "ok"}


def test_openapi_contract(client):
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert paths.keys() >= {"/api/health/live", "/api/health/ready"}
    assert set(paths["/api/health/ready"]["get"]["responses"]) == {"200", "503"}
