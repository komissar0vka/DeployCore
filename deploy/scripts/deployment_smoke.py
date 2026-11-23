"""Exercise the transport-only queue against isolated PostgreSQL."""
import concurrent.futures
import secrets
import subprocess
import uuid


def exercise_deployments(check, login, sql, compose, version_id, admin):
    first_cookie, first_csrf, _ = login("operator")
    second_cookie, second_csrf, _ = login("operator")
    operators = [{"cookie": first_cookie, "csrf": first_csrf}, {"cookie": second_cookie, "csrf": second_csrf}]
    viewer_cookie, viewer_csrf, _ = login("viewer")
    viewer = {"cookie": viewer_cookie, "csrf": viewer_csrf}
    devices = [str(uuid.uuid4()), str(uuid.uuid4())]
    credentials = [secrets.token_urlsafe(32), secrets.token_urlsafe(32)]
    token = check("/enrollment-tokens", {201}, method="POST", **operators[0],
                  data={"label": "Queue smoke", "max_uses": len(devices)})[1]["token"]
    for i, device in enumerate(devices):
        check("/agent/enroll", {200}, method="POST", origin=None, data={
            "installation_id": device, "enrollment_token": token, "credential": credentials[i],
            "heartbeat": {"hostname": f"QUEUE-{i + 1}", "ips": [], "domain_joined": False,
                          "os_version": "Windows 10.0.26100", "agent_version": "0.3.3", "uptime_seconds": 0},
        })

    def agent(i, tail, data=None, expected=200, credential=None):
        return check(f"/agent/{devices[i]}/jobs/{tail}", {expected}, method="POST", data=data, origin=None,
                     extra={"Authorization": f"Bearer {credential or credentials[i]}"})[1]

    def submit(data, operator=operators[0]):
        return check("/deployments", {201}, method="POST", data=data, **operator)[1]

    def request(targets=devices, operation="install"):
        return {"version_id": version_id, "operation": operation, "device_ids": targets, "request_id": str(uuid.uuid4())}

    def expire(attempt):
        sql(f"UPDATE deployment_attempts SET lease_expires_at=clock_timestamp()-interval '2 seconds' WHERE id='{attempt}';")

    check("/deployments", {401})
    check("/deployments", {403}, method="POST", data=request(), **viewer)
    check("/deployments", {403}, method="POST", data=request(), cookie=first_cookie)
    check("/deployments", {422}, method="POST", data=request([devices[0], devices[0]]), **operators[0])
    check("/deployments", {422}, method="POST", data=request([str(uuid.uuid4())]), **operators[0])
    check("/deployments", {409}, method="POST", data={**request(), "version_id": str(uuid.uuid4())}, **operators[0])
    payload = request()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        definitions = list(pool.map(lambda op: submit(payload, op), operators))
    first = definitions[0]
    assert definitions[1]["id"] == first["id"] and first["counts"] == {"queued": 2}
    check("/deployments", {409}, method="POST", data={**payload, "device_ids": devices[:1]}, **operators[0])
    second = submit(request([devices[0]], "uninstall"))
    first_path, second_path = f'/deployments/{first["id"]}', f'/deployments/{second["id"]}'
    assert check("/deployments", {200}, **viewer)[1]["active"] == 2
    check(first_path + "/cancel", {403}, method="POST", **viewer)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        leases = list(pool.map(lambda _: agent(0, "poll")["assignment"], range(8)))
    leased = leases[0]
    assert all(item == leased for item in leases) and leased["mode"] == "transport_only"
    initial = check(first_path, {200}, **viewer)[1]
    assert initial["counts"] == {"leased": 1, "queued": 1}
    expire(leased["attempt_id"])
    agent(0, leased["target_id"] + "/ack", {"attempt_id": leased["attempt_id"]}, 409)
    reissued = agent(0, "poll")["assignment"]
    assert reissued["target_id"] == leased["target_id"] and reissued["attempt_id"] != leased["attempt_id"]
    route = reissued["target_id"]
    proof = {"attempt_id": reissued["attempt_id"]}
    agent(1, route + "/ack", proof, 404)
    agent(0, route + "/ack", proof, 401, credential=credentials[1])
    agent(0, route + "/heartbeat", proof, 409)
    agent(0, route + "/result", {**proof, "outcome": "not_executed"}, 409)
    agent(0, route + "/ack", proof)
    agent(0, route + "/ack", proof)
    agent(0, route + "/result", {**proof, "outcome": "succeeded"}, 422)
    expire(proof["attempt_id"])
    assert agent(0, "poll") == {"assignment": None, "recovery_required": True}
    recover = check(first_path, {200}, **viewer)[1]
    assert next(row for row in recover["targets"] if row["device_id"] == devices[0])["recovery_required"]
    result = check(first_path + "/cancel", {200}, method="POST", **operators[0])[1]
    assert result["counts"] == {"running": 1, "cancelled": 1}
    assert agent(0, route + "/heartbeat", proof)["cancel_requested"]
    completed = {**proof, "outcome": "cancelled"}
    assert agent(0, route + "/result", completed) == completed
    assert agent(0, route + "/result", completed) == completed
    agent(0, route + "/result", {**proof, "outcome": "not_executed"}, 409)
    assert check(first_path, {200}, **viewer)[1]["counts"] == {"cancelled": 2}
    history = check(first_path + "/events", {200}, **viewer)[1]
    actions = [row["action"] for row in history]
    assert actions.count("acknowledged") == 1 and actions.count("cancelled") == 2
    assert {"created", "leased", "lease_expired", "recovered", "cancel_requested"} <= set(actions)
    older = check(first_path + f'/events?before={history[0]["id"]}', {200}, **viewer)[1]
    assert older == history[1:]
    assert agent(1, "poll")["assignment"] is None

    pending = agent(0, "poll")["assignment"]
    assert pending["operation"] == "uninstall" and pending["target_id"] != route
    proof2 = {"attempt_id": pending["attempt_id"]}
    agent(0, pending["target_id"] + "/ack", proof2)
    # Simulate server restart while the agent's durable journal retains the attempt.
    subprocess.run([*compose, "restart", "server"], check=True)
    subprocess.run([*compose, "up", "-d", "--no-build", "--wait", "--wait-timeout", "90"], check=True)
    assert agent(0, pending["target_id"] + "/heartbeat", proof2)["cancel_requested"] is False
    assert agent(0, pending["target_id"] + "/result", {**proof2, "outcome": "not_executed"})["outcome"] == "not_executed"
    assert check(second_path, {200}, **viewer)[1]["counts"] == {"not_executed": 1}

    failed = submit(request(devices[:1]))
    for _ in range(5):
        fresh = agent(0, "poll")["assignment"]
        expire(fresh["attempt_id"])
    assert agent(0, "poll")["assignment"] is None
    assert check(f'/deployments/{failed["id"]}', {200}, **viewer)[1]["counts"] == {"failed": 1}
    assert check("/deployments", {200}, **viewer)[1]["active"] == 0
    audit = check("/audit", {200}, **admin)[1]
    assert [entry["action"] for entry in audit].count("deployment_created") == 3
    assert any(entry["action"] == "deployment_cancelled" for entry in audit)
    print("Deployment API, RBAC, concurrent delivery, idempotency, recovery, cancellation and restart passed")
