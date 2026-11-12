"""Same-process diagnostic checks and durable failure/compilation regressions."""
import asyncio
import errno
import json
import os
import socket
import ssl

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import Settings
from app.execution import network
from app.main import create_app
from app.models.rai import RaiProposal
from app.rai import provider as module
from app.rai.provider import GeminiProvider, ProviderError
from app.rai.designer import create_proposal
from app.schemas.rai import ProposalCreate
from test_rai import agent, design_data, generated

KEY = "private-reliability-test-key"


def wire(output):
    body = {"candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [{"text": json.dumps(output)}]}}]}
    return httpx.Response(200, headers={"content-type": "application/json"}, stream=httpx.ByteStream(json.dumps(body).encode()))


def install_transport(monkeypatch, handler):
    async def resolve(host):
        assert host == "generativelanguage.googleapis.com"
        return "93.184.216.34"
    monkeypatch.setattr(module, "resolve_public", resolve)
    monkeypatch.setattr(module.httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(handler))


def configure(client):
    settings = client.app.state.settings
    settings.rai_provider = "gemini"
    settings.rai_model = "gemini-3.5-flash-lite"
    settings.rai_api_key = SecretStr(KEY)


@pytest.mark.parametrize("cause,wrapper,code", [
    (PermissionError(KEY), httpx.ConnectError, "provider_network_denied"),
    (OSError(errno.EPERM, KEY), httpx.ReadTimeout, "provider_network_denied"),
    (ssl.SSLCertVerificationError(KEY), httpx.ConnectError, "provider_tls_error"),
    (socket.gaierror(KEY), httpx.ConnectError, "provider_dns_error"),
    (None, httpx.ProxyError, "provider_proxy_error"),
    (None, httpx.ReadTimeout, "provider_timeout"),
    (None, httpx.ConnectError, "provider_unreachable"),
])
def test_transport_classification_and_retry_bound(monkeypatch, caplog, cause, wrapper, code):
    calls = []
    def handler(request):
        calls.append(request)
        raise wrapper(KEY) from cause
    install_transport(monkeypatch, handler)
    adapter = GeminiProvider(Settings(_env_file=None, rai_provider="gemini", rai_model="gemini-3.5-flash-lite", rai_api_key=SecretStr(KEY)))
    with pytest.raises(ProviderError) as error:
        asyncio.run(adapter.generate("designer", "private prompt", {}, {}))
    assert error.value.code == code
    assert len(calls) == (2 if code in {"provider_timeout", "provider_unreachable"} else 1)
    assert KEY not in caplog.text and "private prompt" not in caplog.text
    if code == "provider_network_denied":
        assert not any('"phase": "provider_timeout"' in record.getMessage() for record in caplog.records)


def test_permission_denial_during_dns_keeps_its_classification(monkeypatch):
    def denied(*args, **kwargs): raise PermissionError(errno.EACCES, KEY)
    monkeypatch.setattr(network.socket, "getaddrinfo", denied)
    monkeypatch.setattr(module, "resolve_public", network.resolve_public)
    settings = Settings(_env_file=None, rai_provider="gemini", rai_model="gemini-3.5-flash-lite", rai_api_key=SecretStr(KEY))
    with pytest.raises(ProviderError) as error:
        asyncio.run(GeminiProvider(settings).check_connectivity())
    assert error.value.code == "provider_network_denied"


@pytest.mark.parametrize("environment", ["test", "production"])
def test_diagnostics_absent_outside_development(environment):
    options = {"database_url": "sqlite:///:memory:"} if environment == "test" else {
        "database_url": "postgresql://test:test@localhost/test",
        "cors_origins": ["https://demo.example.com"],
        "workspace_access_token": "synthetic-workspace-" + "w" * 40,
    }
    settings = Settings(_env_file=None, environment=environment, **options)
    headers = {} if environment == "test" else {"X-Testah-Workspace-Token": settings.workspace_access_token.get_secret_value()}
    with TestClient(create_app(settings), headers=headers) as client:
        assert client.post("/api/rai/diagnostics", json={"run_smoke_test": True}).status_code == 404
        specification = client.get("/openapi.json")
        if environment == "production":
            assert specification.status_code == 404
        else:
            assert "/api/rai/diagnostics" not in specification.json()["paths"]
        assert not client.get("/api/rai/configuration").json()["diagnostics_available"]


def test_diagnostics_are_explicit_use_the_same_process_and_never_send_key_to_probe(agent_client, monkeypatch):
    configure(agent_client)
    calls = []
    def handler(request):
        calls.append(request)
        assert os.getpid() == agent_client.app.state.provider_diagnostics.runtime["pid"]
        assert request.url.host == "93.184.216.34" and not request.url.query
        assert request.extensions["sni_hostname"] == "generativelanguage.googleapis.com"
        assert request.headers["host"] == "generativelanguage.googleapis.com"
        if request.method == "GET":
            assert "x-goog-api-key" not in request.headers
            return httpx.Response(404)
        assert request.headers["x-goog-api-key"] == KEY
        generation = json.loads(request.content)["generationConfig"]
        assert generation["maxOutputTokens"] == 256
        return wire({"ok": True})
    install_transport(monkeypatch, handler)
    agent_client.get("/api/health"); agent_client.get("/api/rai/configuration")
    assert calls == []
    response = agent_client.post("/api/rai/diagnostics", json={"run_smoke_test": True})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["connectivity"]["code"] == "https_reached" and data["connectivity"]["http_status"] == 404
    assert data["smoke_test"]["code"] == "authenticated_generation_succeeded"
    assert data["key_configured"] and data["runtime"]["pid"] == os.getpid()
    assert data["smoke_test"]["latency_ms"] >= 0 and len(calls) == 2
    assert KEY not in response.text and "x-goog-api-key" not in response.text
    assert agent_client.get("/api/environments").json() == []


@pytest.mark.parametrize("problem,expected", [("denied", "provider_network_denied"), ("timeout", "provider_timeout"),
                                             ("authentication", "provider_authentication_failed"), ("invalid", "invalid_model_output")])
def test_diagnostic_failure_is_sanitized_and_lock_released(agent_client, monkeypatch, problem, expected):
    configure(agent_client)
    def handler(request):
        if request.method == "GET":
            if problem == "denied": raise httpx.ConnectError(KEY) from PermissionError(KEY)
            return httpx.Response(404)
        if problem == "timeout": raise httpx.ReadTimeout(KEY)
        if problem == "authentication": return httpx.Response(403, text=KEY)
        return wire({"ok": False})
    install_transport(monkeypatch, handler)
    response = agent_client.post("/api/rai/diagnostics", json={"run_smoke_test": True})
    data = response.json()
    check = data["connectivity"] if problem == "denied" else data["smoke_test"]
    assert check["status"] == "failed" and check["code"] == expected and check["message"]
    if problem == "denied": assert data["smoke_test"]["status"] == "skipped"
    assert KEY not in response.text
    assert not agent_client.app.state.provider_diagnostics.running
    assert agent_client.get("/api/health").status_code == 200


def test_diagnostics_reject_cross_site_and_concurrent_checks(agent_client):
    assert agent_client.post("/api/rai/diagnostics", json={"run_smoke_test": True}, headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert agent_client.post("/api/rai/diagnostics", json={}).status_code == 422
    agent_client.app.state.provider_diagnostics.running = True
    assert agent_client.post("/api/rai/diagnostics", json={"run_smoke_test": True}).status_code == 409
    agent_client.app.state.provider_diagnostics.running = False


def test_mock_diagnostics_do_not_call_gemini(agent_client, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("Mock must not use network")
    monkeypatch.setattr(module, "resolve_public", forbidden)
    data = agent_client.post("/api/rai/diagnostics", json={"run_smoke_test": True}).json()
    assert data["is_mock"] and data["smoke_test"]["status"] == "skipped"


@pytest.mark.parametrize("problem,expected", [("denied", "provider_network_denied"), ("timeout", "provider_timeout"),
                                             ("invalid", "invalid_model_output"), ("success", "validated")])
def test_generation_failure_is_atomic_and_explicit_retry_can_succeed(agent_client, monkeypatch, problem, expected):
    configure(agent_client)
    output = design_data()
    failing = True
    def handler(request):
        if failing:
            if problem == "denied": raise httpx.ConnectError(KEY) from PermissionError(KEY)
            if problem == "timeout": raise httpx.ReadTimeout(KEY)
            if problem == "invalid":
                return httpx.Response(200, headers={"content-type": "application/json"}, stream=httpx.ByteStream(b"invalid JSON"))
        return wire(output)
    install_transport(monkeypatch, handler)
    candidate = agent(agent_client)
    proposal = generated(agent_client, candidate)
    assert proposal["validation"]["code"] == expected
    if problem != "success":
        assert proposal["status"] == "failed" and proposal["preview"] is None and proposal["environment_id"] is None
        assert proposal["validation"]["message"]
        assert agent_client.post(f"/api/rai/proposals/{proposal['id']}/compile").status_code == 409
        with agent_client.app.state.session_factory() as session:
            row = session.scalar(select(RaiProposal).where(RaiProposal.id == proposal["id"]))
            assert row.proposal_json is None and row.blueprint_json is None and row.lease_token is None
        assert agent_client.get("/api/environments").json() == []
        failing = False
        recovered = generated(agent_client, candidate)
        assert recovered["id"] != proposal["id"] and recovered["status"] == "ready"
    else:
        recovered = proposal
    compiled = agent_client.post(f"/api/rai/proposals/{recovered['id']}/compile").json()
    assert compiled["status"] == "compiled" and compiled["provider"] == "gemini" and not compiled["is_mock"]
    assert len(agent_client.get("/api/environments").json()) == 1
    assert KEY not in json.dumps(compiled)


def test_worker_shutdown_discards_inflight_design_and_releases_lease(agent_client):
    candidate = agent(agent_client)
    worker = agent_client.app.state.designer_worker
    proposal, token = create_proposal(worker.factory, ProposalCreate(agent_id=candidate["id"], request_key="shutdown-regression"), worker.settings)
    async def run():
        started = asyncio.Event()
        class WaitingProvider:
            async def generate(self, purpose, instructions, data, schema):
                started.set()
                await asyncio.Event().wait()
        worker.provider_override = WaitingProvider()
        worker.submit(proposal.id, token)
        await started.wait()
        await worker.close()
    asyncio.run(run())
    result = agent_client.get("/api/rai/proposals/" + proposal.id).json()
    assert result["status"] == "failed" and result["validation"]["code"] == "generation_worker_stopped"
    assert result["preview"] is None and result["environment_id"] is None
    assert agent_client.get("/api/environments").json() == []
    with worker.factory() as session:
        row = session.get(RaiProposal, proposal.id)
        assert row.lease_token is None and row.blueprint_json is None and row.proposal_json is None
