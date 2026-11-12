import asyncio
from datetime import timedelta
import json

import pytest
from pydantic import SecretStr
from sqlalchemy.exc import OperationalError
from app.core.domain_errors import ServiceError
from app.events.store import append_event
from app.events.stream import AssessmentStreams, frame, MAX_FRAME_BYTES
from app.database.session import build_engine, make_session_factory
from app.execution.service import locked_run, start_assessment, transition
from app.models.agent import Agent, utcnow
from test_rai import agent

TOKEN = "monitor-test-only-" + "x" * 40
AUTH = {"Authorization": "Bearer " + TOKEN}


def make_run(client):
    client.app.state.settings.monitor_token = SecretStr(TOKEN)
    candidate = agent(client)
    with client.app.state.session_factory() as session, session.begin():
        session.get(Agent, candidate["id"]).last_test_status = "connected"
    environment = client.post("/api/environments", json={"name": "Stream fixture", "template_id": "budget_constrained_purchase"}).json()
    response = client.post("/api/assessments", json={"agent_id": candidate["id"], "environment_id": environment["id"]})
    assert response.status_code == 201, response.text
    return response.json()


def finish(client, run_id, status="completed", count=0):
    factory = client.app.state.session_factory
    _, token = start_assessment(factory, run_id, client.app.state.settings)
    with locked_run(factory, run_id, token) as (session, run):
        for number in range(count): append_event(session, run, "test.recorded", {"number": number})
        transition(session, run, status, "stream_fixture")


def frames(content):
    result = []
    for block in content.split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line and not line.startswith(":"))
        if "data" in fields: result.append({**fields, "data": json.loads(fields["data"])})
    return result


def evidence(content):
    return [item["data"] for item in frames(content) if item.get("event") == "assessment_event"]


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled", "inconclusive"])
def test_terminal_stream_drains_ordered_history_and_closes(agent_client, status):
    run = make_run(agent_client); finish(agent_client, run["id"], status, count=205)
    response = agent_client.get(f"/api/assessments/{run['id']}/stream", headers=AUTH)
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache, no-store" and response.headers["x-accel-buffering"] == "no"
    events = evidence(response.text)
    assert events == agent_client.get(f"/api/assessments/{run['id']}/events?limit=500").json()
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert len({event["id"] for event in events}) == len(events)
    assert frames(response.text)[-1]["data"] == {"run_id": run["id"], "status": status, "last_sequence": len(events)}
    assert agent_client.app.state.assessment_streams.active == 0


def test_cursor_resume_last_event_id_precedence_and_isolation(agent_client):
    run = make_run(agent_client); other = make_run(agent_client)
    finish(agent_client, run["id"]); finish(agent_client, other["id"])
    path = f"/api/assessments/{run['id']}/stream"
    history = agent_client.get(f"/api/assessments/{run['id']}/events").json()
    by_sequence = agent_client.get(path + "?after_sequence=2", headers=AUTH)
    by_id = agent_client.get(path + "?after_sequence=999", headers={**AUTH, "Last-Event-ID": history[1]["id"]})
    assert evidence(by_sequence.text) == evidence(by_id.text) == history[2:]
    at_end = agent_client.get(path, headers={**AUTH, "Last-Event-ID": history[-1]["id"]})
    assert evidence(at_end.text) == [] and frames(at_end.text)[-1]["event"] == "settled"
    other_id = agent_client.get(f"/api/assessments/{other['id']}/events").json()[0]["id"]
    assert agent_client.get(path, headers={**AUTH, "Last-Event-ID": other_id}).status_code == 422
    assert agent_client.get(path + "?after_sequence=999", headers=AUTH).status_code == 422
    assert agent_client.get(path + "?after_sequence=-1", headers=AUTH).status_code == 422
    assert agent_client.app.state.assessment_streams.active == 0


def test_stream_authentication_configuration_and_cors(agent_client):
    assert agent_client.get("/api/assessments/missing/stream").status_code == 503
    run = make_run(agent_client)
    for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic wrong"}):
        assert agent_client.get("/api/assessments/missing/stream", headers=headers).status_code == 401
    assert agent_client.get("/api/assessments/missing/stream", headers=AUTH).status_code == 404
    preflight = agent_client.options(f"/api/assessments/{run['id']}/stream", headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization,last-event-id"})
    assert preflight.status_code == 200
    assert agent_client.get(f"/api/assessments/{run['id']}/stream?token={TOKEN}").status_code == 401


def test_shared_public_sanitization_and_no_private_run_aggregate(agent_client):
    run = make_run(agent_client)
    key = "private-provider-fixture-key"
    agent_client.app.state.settings.rai_api_key = SecretStr(key)
    with locked_run(agent_client.app.state.session_factory, run["id"]) as (session, row):
        append_event(session, row, "test.recorded", {"api_key": key, "copy": TOKEN + " " + key,
                     "payment_credentials": "private-value", "endpoint_url": "https://private.example/path"}, correlation_id=key)
    finish(agent_client, run["id"])
    response = agent_client.get(f"/api/assessments/{run['id']}/stream", headers=AUTH)
    assert all(value not in response.text for value in (key, TOKEN, "private-value", "private.example", "runtime_json", "blueprint_json", "lease_token", "agent_config"))
    assert evidence(response.text) == agent_client.get(f"/api/assessments/{run['id']}/events").json()


def test_created_connection_heartbeats_then_receives_start_and_cancel(agent_client):
    run = make_run(agent_client)
    # Measure the stream's pool, independently of the evaluation worker's polling.
    engine = build_engine(str(agent_client.app.state.engine.url))
    streams = AssessmentStreams(make_session_factory(engine), agent_client.app.state.settings)
    streams.poll_seconds = .01; streams.heartbeat_seconds = .02
    async def run_test():
        async def connected(): return False
        iterator = streams.iterate(run["id"], 0, connected, streams.reserve())
        output = []
        while True:
            chunk = await asyncio.wait_for(anext(iterator), 2); output.append(chunk)
            if chunk.startswith(": heartbeat"): break
        assert streams.active == 1 and engine.pool.checkedout() == 0
        # A real state mutation after the client connected; no execution is scheduled by monitoring.
        _, token = start_assessment(streams.factory, run["id"], streams.settings)
        with locked_run(streams.factory, run["id"], token) as (session, record): transition(session, record, "cancelled", "user_cancelled")
        output.extend([chunk async for chunk in iterator])
        assert frames("".join(output))[-1]["data"]["status"] == "cancelled"
        assert [event["sequence"] for event in evidence("".join(output))] == [1, 2, 3, 4]
        assert streams.active == 0
    try:
        asyncio.run(run_test())
    finally:
        engine.dispose()


def test_concurrent_readers_receive_identical_isolated_history(agent_client):
    run = make_run(agent_client); other = make_run(agent_client); finish(agent_client, run["id"], count=10)
    streams = agent_client.app.state.assessment_streams
    async def collect():
        async def connected(): return False
        return "".join([chunk async for chunk in streams.iterate(run["id"], 0, connected, streams.reserve())])
    async def both(): return await asyncio.gather(collect(), collect())
    first, second = asyncio.run(both())
    assert evidence(first) == evidence(second) and streams.active == 0
    assert all(event["run_id"] == run["id"] and event["run_id"] != other["id"] for event in evidence(first))


def test_disconnect_and_cancellation_release_slots_and_database_connections(agent_client):
    run = make_run(agent_client); streams = agent_client.app.state.assessment_streams
    streams.poll_seconds = .01
    async def run_test():
        disconnected = False
        async def check(): return disconnected
        iterator = streams.iterate(run["id"], 0, check, streams.reserve())
        await anext(iterator); await anext(iterator); await anext(iterator)
        disconnected = True
        with pytest.raises(StopAsyncIteration): await anext(iterator)
        assert streams.active == 0
        disconnected = False
        iterator = streams.iterate(run["id"], 1, check, streams.reserve())
        await anext(iterator); await anext(iterator)
        waiting = asyncio.create_task(anext(iterator)); await asyncio.sleep(.02); waiting.cancel()
        with pytest.raises(asyncio.CancelledError): await waiting
        await iterator.aclose()
        assert streams.active == 0 and agent_client.app.state.engine.pool.checkedout() == 0
    asyncio.run(run_test())


def test_actual_asgi_disconnect_cleans_up_stream(agent_client):
    run = make_run(agent_client); streams = agent_client.app.state.assessment_streams
    async def run_test():
        disconnect = asyncio.Event(); requested = False
        async def receive():
            nonlocal requested
            if not requested:
                requested = True; return {"type": "http.request", "body": b"", "more_body": False}
            await disconnect.wait(); return {"type": "http.disconnect"}
        async def send(message):
            if message["type"] == "http.response.body" and b"assessment_event" in message.get("body", b""): disconnect.set()
        scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.0"}, "http_version": "1.1", "scheme": "http", "method": "GET",
            "path": f"/api/assessments/{run['id']}/stream", "raw_path": b"/", "query_string": b"", "root_path": "",
            "headers": [(b"authorization", ("Bearer " + TOKEN).encode())], "client": ("127.0.0.1", 12345), "server": ("127.0.0.1", 8000)}
        await asyncio.wait_for(agent_client.app(scope, receive, send), 3)
        assert streams.active == 0
    asyncio.run(run_test())


def test_expired_worker_uses_existing_recovery_and_settles_inconclusive(agent_client):
    run = make_run(agent_client); factory = agent_client.app.state.session_factory
    _, token = start_assessment(factory, run["id"], agent_client.app.state.settings)
    with locked_run(factory, run["id"], token) as (_session, row): row.lease_expires_at = utcnow() - timedelta(seconds=1)
    response = agent_client.get(f"/api/assessments/{run['id']}/stream", headers=AUTH)
    assert frames(response.text)[-1]["data"]["status"] == "inconclusive"
    assert any(event["payload"].get("reason") == "worker_lease_expired" for event in evidence(response.text))
    assert not agent_client.app.state.worker.tasks


def test_stream_limits_and_database_errors_are_safe(agent_client, monkeypatch):
    run = make_run(agent_client); streams = agent_client.app.state.assessment_streams
    leases = [streams.reserve() for _ in range(streams.settings.monitor_max_streams)]
    assert agent_client.get(f"/api/assessments/{run['id']}/stream", headers=AUTH).status_code == 503
    for lease in leases: lease.close()
    def broken(*args): raise OperationalError("private sql", {}, Exception("private details"))
    monkeypatch.setattr(streams, "read", broken)
    response = agent_client.get(f"/api/assessments/{run['id']}/stream", headers=AUTH)
    assert frames(response.text)[-1]["data"]["code"] == "event_store_unavailable" and "private" not in response.text
    assert streams.active == 0
    with pytest.raises(ServiceError): frame("assessment_event", {"value": "x" * MAX_FRAME_BYTES})


def test_missing_tail_is_reported_instead_of_hanging_a_terminal_stream(agent_client):
    run = make_run(agent_client); finish(agent_client, run["id"])
    with locked_run(agent_client.app.state.session_factory, run["id"]) as (_session, row): row.event_sequence += 1
    response = agent_client.get(f"/api/assessments/{run['id']}/stream", headers=AUTH)
    assert frames(response.text)[-1]["event"] == "stream_error"
    assert frames(response.text)[-1]["data"]["code"] == "event_history_gap"
    assert agent_client.app.state.assessment_streams.active == 0
