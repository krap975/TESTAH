import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.execution.connector import connection_probe
from app.schemas.protocol import AgentRequest, response_adapter

ROOT = Path(__file__).resolve().parents[2]

def test_request_supports_context_history_and_previous_result():
    payload = connection_probe().model_dump()
    payload["history"] = [{"role":"assistant", "content":"Earlier reply"}]
    payload["previous_tool_result"] = {"correlation_id":"call-1", "name":"test_echo", "status":"success", "result":{"text":"earlier"}}
    request = AgentRequest.model_validate(payload)
    assert request.previous_tool_result.correlation_id == "call-1"
    assert request.available_tools[0].input_schema["type"] == "object"

@pytest.mark.parametrize("change", ["version_missing", "version_wrong", "extra", "numeric_id", "bad_history", "bad_tool", "bad_previous"])
def test_request_schema_is_strict(change):
    payload = connection_probe().model_dump()
    if change == "version_missing": del payload["protocol_version"]
    if change == "version_wrong": payload["protocol_version"] = "2.0"
    if change == "extra": payload["private_instruction"] = True
    if change == "numeric_id": payload["request_id"] = 123
    if change == "bad_history": payload["history"] = [{"role":"system", "content":"Not permitted"}]
    if change == "bad_tool": payload["available_tools"][0]["description"] = 123
    if change == "bad_previous": payload["previous_tool_result"] = {"status":"paid"}
    with pytest.raises(ValidationError): AgentRequest.model_validate(payload)

def test_sample_agent_works_without_backend_and_supports_auth(monkeypatch):
    # Only the sample process and shared wire schemas are imported, not the API/database.
    import sys
    sys.path.insert(0, str(ROOT))
    from sample_agents.main import app
    monkeypatch.delenv("TESTAH_SAMPLE_TOKEN", raising=False)
    with TestClient(app) as sample:
        for kind in ("message", "tool_call", "completed"):
            request = connection_probe(kind)
            response = sample.post("/agent", json=request.model_dump())
            assert response.status_code == 200
            assert response_adapter.validate_python(response.json()).type == kind
        monkeypatch.setenv("TESTAH_SAMPLE_TOKEN", "Bearer sample-test-token")
        assert sample.post("/agent", json=connection_probe().model_dump()).status_code == 401
        assert sample.post("/agent", json=connection_probe().model_dump(), headers={"Authorization":"Bearer sample-test-token"}).status_code == 200

