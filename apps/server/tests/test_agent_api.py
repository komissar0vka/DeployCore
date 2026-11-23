import pytest
from fastapi.testclient import TestClient

from deploycore.body_limit import AGENT_BODY_LIMIT
from deploycore.device_schemas import Disk, Heartbeat
from deploycore.main import app
from pydantic import ValidationError


def test_agent_request_size_is_limited_before_parsing(monkeypatch):
    for name in ("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        monkeypatch.setenv(name, "unused")
    with TestClient(app) as client:
        response = client.post("/api/v1/agent/enroll", content=b"x" * (AGENT_BODY_LIMIT + 1))
    assert response.status_code == 413
    assert response.json() == {"detail": "body_too_large"}


def test_inventory_rejects_invalid_free_space():
    with pytest.raises(ValidationError):
        Disk(letter="C:", size_bytes=50, free_bytes=51)


def test_heartbeat_does_not_accept_client_timestamps():
    with pytest.raises(ValidationError) as failure:
        Heartbeat.model_validate({
            "hostname": "WORKSTATION", "domain_joined": False, "ips": [], "os_version": "Windows 10.0",
            "agent_version": "0.3.0", "uptime_seconds": 0, "last_seen_at": "2100-01-01",
        })
    assert failure.value.errors()[0]["type"] == "extra_forbidden"
