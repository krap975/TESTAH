import json
import socket
import anyio
import httpx
import pytest
from pydantic import SecretStr
from app.execution import connector, network
from app.execution.connector import AgentConnector, connection_probe, get_connector
from app.models.agent import Agent
from app.schemas.protocol import AgentRequest, response_adapter
from test_agents import create

PUBLIC_IP = "93.184.216.34"

def response_body(request, kind="message"):
    sent = json.loads(request.content)
    data = {"protocol_version": "1.0", "request_id": sent["request_id"], "session_id": sent["session_id"], "type": kind}
    if kind == "message": data["message"] = "Hello"
    elif kind == "completed": data["summary"] = "Claimed finished; not an evaluation"
    else: data["tool_call"] = {"correlation_id": "call-1", "name": "test_echo", "arguments": {"text": "hello"}}
    return data

def wire_response(data, status=200, headers=None):
    return httpx.Response(status, headers={"content-type": "application/json", **(headers or {})}, stream=httpx.ByteStream(json.dumps(data).encode()))

@pytest.fixture
def mock_dns(monkeypatch):
    calls = []
    def resolver(host, port, **kwargs):
        calls.append((host, port))
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, 443))]
    monkeypatch.setattr(network.socket, "getaddrinfo", resolver)
    return calls

def override(client, handler):
    client.app.dependency_overrides[get_connector] = lambda: AgentConnector(client.app.state.settings, httpx.MockTransport(handler))

def run_test(client):
    record = create(client).json()
    return record, client.post("/api/agents/" + record["id"] + "/test")

@pytest.mark.parametrize("kind", ["message", "tool_call", "completed"])
def test_protocol_success_and_dns_pinning(agent_client, mock_dns, kind):
    seen = []
    def handler(request):
        seen.append(request)
        assert request.url.host == PUBLIC_IP
        assert request.headers["host"] == "agents.example.com"
        assert request.extensions["sni_hostname"] == "agents.example.com"
        return wire_response(response_body(request, kind))
    override(agent_client, handler)
    record, response = run_test(agent_client)
    assert response.status_code == 200, response.text
    assert response.json()["response_type"] == kind
    assert len(mock_dns) == 1 and len(seen) == 1
    saved = agent_client.get("/api/agents/" + record["id"]).json()
    assert saved["last_test_status"] == "connected" and saved["last_test_at"]
    metadata_only = agent_client.patch("/api/agents/" + record["id"], json={"description": "Updated details", "endpoint_url": record["endpoint_url"], "connection_mode": record["connection_mode"]}).json()
    assert metadata_only["last_test_status"] == "connected"
    assert metadata_only["last_test_at"] == saved["last_test_at"]
    updated = agent_client.patch("/api/agents/" + record["id"], json={"endpoint_url": "https://agents.example.com/new"}).json()
    assert updated["last_test_status"] == "not_tested" and updated["last_test_at"] is None

@pytest.mark.parametrize("status,code", [(301,"redirect_rejected"), (307,"redirect_rejected"), (401,"authentication_rejected"), (403,"authentication_rejected"), (500,"agent_http_error")])
def test_http_errors_never_follow_redirects(agent_client, mock_dns, status, code):
    seen = []
    def handler(request):
        seen.append(request)
        return wire_response({"private": "untrusted body"}, status=status, headers={"Location": "http://169.254.169.254/latest"})
    override(agent_client, handler)
    record, response = run_test(agent_client)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == code
    assert len(seen) == 1 and "untrusted body" not in response.text
    assert agent_client.get("/api/agents/" + record["id"]).json()["last_test_code"] == code

@pytest.mark.parametrize("exception,code,status", [(httpx.ConnectError("private"),"unreachable",502), (httpx.ReadTimeout("private"),"timeout",504)])
def test_network_failures(agent_client, mock_dns, exception, code, status):
    def handler(_request): raise exception
    override(agent_client, handler)
    _, response = run_test(agent_client)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "private" not in response.text

@pytest.mark.parametrize("case", ["extra", "missing", "version", "ids", "type", "arguments", "unknown_tool", "json", "duplicate", "media", "compression"])
def test_malformed_protocol(agent_client, mock_dns, case):
    def handler(request):
        data = response_body(request, "tool_call")
        if case == "extra": data["unexpected"] = True
        if case == "missing": del data["request_id"]
        if case == "version": data["protocol_version"] = "2.0"
        if case == "ids": data["session_id"] = "wrong"
        if case == "type": data["type"] = "payment_success"
        if case == "arguments": data["tool_call"]["arguments"] = "not an object"
        if case == "unknown_tool": data["tool_call"]["name"] = "create_checkout"
        if case in ("json", "duplicate"):
            raw = b"not json" if case == "json" else b'{"type":"message","type":"completed"}'
            return httpx.Response(200, headers={"content-type":"application/json"}, stream=httpx.ByteStream(raw))
        return wire_response(data, headers={"content-type":"text/html"} if case == "media" else {"content-encoding":"gzip"} if case == "compression" else {})
    override(agent_client, handler)
    _, response = run_test(agent_client)
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "invalid_protocol"

@pytest.mark.parametrize("declared", [False, True])
def test_bounded_response(agent_client, mock_dns, declared):
    agent_client.app.state.settings.agent_max_response_bytes = 1024
    override(agent_client, lambda _req: httpx.Response(200, headers={"content-type":"application/json", **({"content-length":"999999"} if declared else {})}, stream=httpx.ByteStream(b"x" * 5000)))
    _, response = run_test(agent_client)
    assert response.json()["error"]["code"] == "response_too_large"

def test_auth_header_and_no_secret_disclosure(agent_client, mock_dns, caplog):
    secret = "Bearer never-return-this"
    agent_client.app.state.settings.agent_secrets = {"KEY": SecretStr(secret)}
    def handler(request):
        assert request.headers["authorization"] == secret
        data = response_body(request)
        data["message"] = secret  # A hostile agent might echo a credential.
        return wire_response(data)
    override(agent_client, handler)
    record = create(agent_client, authentication={"header_name":"Authorization", "secret_key":"KEY"}).json()
    response = agent_client.post("/api/agents/" + record["id"] + "/test")
    assert response.status_code == 200
    assert secret not in response.text and secret not in caplog.text
    assert secret not in agent_client.get("/api/agents").text
    agent_client.app.state.settings.agent_secrets = {}
    response = agent_client.post("/api/agents/" + record["id"] + "/test")
    assert response.json()["error"]["code"] == "secret_unavailable"

@pytest.mark.parametrize("addresses", [["127.0.0.1"], [PUBLIC_IP,"10.1.2.3"], ["169.254.169.254"], ["::ffff:127.0.0.1"], ["100.100.100.200"], ["64:ff9b::a00:1"]])
def test_private_and_mixed_dns_answers_are_blocked(agent_client, monkeypatch, addresses):
    monkeypatch.setattr(network.socket, "getaddrinfo", lambda *_args, **_kwargs: [(socket.AF_INET,1,6,"",(address,443)) for address in addresses])
    def handler(_request): pytest.fail("Blocked destination reached transport")
    override(agent_client, handler)
    _, response = run_test(agent_client)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "destination_blocked"

def test_dns_failure(agent_client, monkeypatch):
    def resolver(*_args, **_kwargs): raise socket.gaierror()
    monkeypatch.setattr(network.socket, "getaddrinfo", resolver)
    override(agent_client, lambda _request: pytest.fail("DNS failure reached transport"))
    _, response = run_test(agent_client)
    assert response.json()["error"]["code"] == "dns_error"

def test_total_deadline(agent_client, mock_dns):
    agent_client.app.state.settings.agent_timeout_seconds = .02
    async def handler(request):
        await anyio.sleep(.2)
        return wire_response(response_body(request))
    override(agent_client, handler)
    _, response = run_test(agent_client)
    assert response.status_code == 504

def test_sample_gate_rechecked_on_use(agent_client):
    agent_client.app.state.settings.allow_local_sample = True
    record = create(agent_client, connection_mode="local_sample", endpoint_url=network.LOCAL_SAMPLE_URL).json()
    agent_client.app.state.settings.allow_local_sample = False
    response = agent_client.post("/api/agents/" + record["id"] + "/test")
    assert response.json()["error"]["code"] == "local_sample_disabled"


def test_concurrent_change_does_not_store_a_stale_test_result(agent_client, mock_dns):
    def handler(request):
        with agent_client.app.state.session_factory() as session:
            agent = session.query(Agent).first()
            agent.endpoint_url = "https://agents.example.com/changed-during-test"
            session.commit()
        return wire_response(response_body(request))
    override(agent_client, handler)
    record, response = run_test(agent_client)
    assert response.status_code == 409, response.text
    saved = agent_client.get("/api/agents/" + record["id"]).json()
    assert saved["endpoint_url"].endswith("changed-during-test")
    assert saved["last_test_status"] == "not_tested"

@pytest.mark.parametrize("raw", [b'{"number":NaN}', b'{"number":1e999}'])
def test_nonfinite_json_is_rejected(agent_client, mock_dns, raw):
    override(agent_client, lambda _req: httpx.Response(200, headers={"content-type":"application/json"}, stream=httpx.ByteStream(raw)))
    _, response = run_test(agent_client)
    assert response.json()["error"]["code"] == "invalid_protocol"

@pytest.mark.parametrize("declared", ["not-a-number", "-1", "9" * 5000])
def test_malformed_or_excessive_content_length_is_safe(agent_client, mock_dns, declared):
    override(agent_client, lambda _req: wire_response({}, headers={"content-length": declared}))
    _, response = run_test(agent_client)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "response_too_large"
