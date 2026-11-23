from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from deploycore.schemas import Role, SettingsInput
from deploycore.security import Permission, require, require_same_origin


@pytest.mark.parametrize(
    ("role", "manage_operations"),
    [(Role.SUPER_ADMIN, True), (Role.ADMINISTRATOR, True), (Role.VIEWER, False)],
)
def test_operation_permission(role, manage_operations):
    user = SimpleNamespace(role=role)
    allowed = require(Permission.MANAGE_OPERATIONS)
    if manage_operations:
        assert allowed((user, None, "")) is user
    else:
        with pytest.raises(HTTPException, match="permission_denied") as error:
            allowed((user, None, ""))
        assert error.value.status_code == 403


@pytest.mark.parametrize("agent_url", [
    "http://server.example",
    "https://user:password@server.example/",
    "https://server.example/path",
    "https://server.example/?query=value",
])
def test_agent_address_must_be_an_https_origin(agent_url):
    with pytest.raises(ValidationError):
        SettingsInput(
            organization="Organization", instance_name="DeployCore", agent_url=agent_url,
            heartbeat_seconds=60, language="ru",
        )


def test_origin_must_include_the_public_port_and_custom_header():
    headers = {"host": "server.example:8443", "origin": "https://server.example:8443"}
    request = SimpleNamespace(headers=headers)
    with pytest.raises(HTTPException, match="request_origin"):
        require_same_origin(request)
    headers["x-deploycore-request"] = "1"
    require_same_origin(request)
    headers["origin"] = "https://server.example"
    with pytest.raises(HTTPException, match="request_origin"):
        require_same_origin(request)
