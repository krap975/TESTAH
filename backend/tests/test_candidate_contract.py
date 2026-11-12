"""Public contract boundary and examples, without database or provider access."""
import copy
import importlib.util
import json
import hashlib
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.schemas.protocol import AgentRequest, response_adapter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("candidate_export", ROOT / "backend/scripts/export_candidate_openapi.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def test_candidate_contract_is_current_and_contains_only_agent_interface():
    contract = json.loads(exporter.DESTINATION.read_text(encoding="utf-8"))
    assert contract == exporter.build_specification()
    assert set(contract["paths"]) == {"/agent"}
    assert set(contract["paths"]["/agent"]) == {"post"}
    assert contract["servers"][0]["url"] == "https://candidate.invalid"
    encoded = json.dumps(contract).lower()
    for forbidden in ("/api/", "paypal", "payment_operator", "monitor_token", "secret_key", "assessment_id", "448a13ed"):
        assert forbidden not in encoded
    # Reference closure prevents accidental omission or inclusion of unrelated models.
    schemas = contract["components"]["schemas"]
    found = set()

    def visit(value):
        if isinstance(value, dict):
            ref = value.get("$ref")
            if ref:
                assert ref.startswith("#/components/schemas/")
                name = ref.rsplit("/", 1)[-1]
                if name not in found:
                    found.add(name)
                    visit(schemas[name])
            for key, child in value.items():
                if key != "$ref":
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(contract["paths"])
    assert found == set(schemas)


def test_published_examples_round_trip_through_real_sample(monkeypatch):
    from sample_agents.main import app
    monkeypatch.delenv("TESTAH_SAMPLE_TOKEN", raising=False)
    with TestClient(app) as client:
        for kind in exporter.RESPONSE_EXAMPLES:
            request = copy.deepcopy(exporter.REQUEST_EXAMPLE)
            request["context"]["sample_response_mode"] = kind
            AgentRequest.model_validate(request)
            documented = response_adapter.validate_python(exporter.RESPONSE_EXAMPLES[kind])
            response = client.post("/agent", json=request)
            assert response.status_code == 200
            actual = response_adapter.validate_python(response.json())
            assert actual.type == documented.type == kind
            assert actual.request_id == request["request_id"]
            assert actual.session_id == request["session_id"]


def test_documentation_changes_preserve_request_and_response_validation_constraints():
    def normalize(value):
        if isinstance(value, dict):
            return {key: normalize(child) for key, child in value.items()
                    if key not in {"$defs", "title", "description", "example", "examples"}
                    # FastAPI omits the annotation default:null; optional/nullable
                    # validation constraints are unchanged and compared below.
                    and not (key == "default" and child is None)}
        if isinstance(value, list):
            return [normalize(child) for child in value]
        return value

    schemas = exporter.build_specification()["components"]["schemas"]
    request = AgentRequest.model_json_schema(ref_template="#/components/schemas/{model}")
    response = response_adapter.json_schema(ref_template="#/components/schemas/{model}", mode="serialization")
    assert normalize(schemas["AgentRequest"]) == normalize(request)
    assert normalize(schemas["AgentResponse"]) == normalize(response)
    for name, original in {**request["$defs"], **response["$defs"]}.items():
        if name == "JsonValue":
            assert normalize(original) == {}
            assert normalize(schemas[name]) == {"anyOf": [{"type": kind} for kind in
                                               ("string", "number", "boolean", "null", "array", "object")]}
        else:
            assert normalize(schemas[name]) == normalize(original)


def test_sample_errors_match_documented_fastapi_shapes(monkeypatch):
    from sample_agents.main import app
    with TestClient(app) as client:
        monkeypatch.setenv("TESTAH_SAMPLE_TOKEN", "Bearer synthetic-contract-test")
        response = client.post("/agent", json=exporter.REQUEST_EXAMPLE)
        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication required."}
        assert client.post("/agent", json=exporter.REQUEST_EXAMPLE,
                           headers={"Authorization": "Bearer synthetic-contract-test"}).status_code == 200
        monkeypatch.delenv("TESTAH_SAMPLE_TOKEN")
        response = client.post("/agent", json={"protocol_version": "1.0"})
        assert response.status_code == 422 and isinstance(response.json()["detail"], list)


def test_actual_apimatic_artifact_hashes_match_provenance():
    manifest = json.loads((ROOT / "docs/apimatic/provenance/manifest.json").read_text(encoding="utf-8"))
    assert manifest["validation_exit_code"] == manifest["generation_exit_code"] == 0
    assert manifest["generator"] == "APIMatic CLI 1.5.0"
    for name, digest in {**manifest["artifact"], **manifest["generated_files"]}.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    for name, digest in manifest["inputs"].items():
        if name.startswith("tmp/phase10-apimatic-input/src/"):
            relative = name.removeprefix("tmp/phase10-apimatic-input/src/")
            source = exporter.DESTINATION if relative.startswith("spec/") else ROOT / "docs/apimatic/src" / relative
        else:
            source = ROOT / name
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest


def test_actual_generated_examples_execute_against_sample(monkeypatch):
    from sample_agents.main import app
    portal = ROOT / "docs/apimatic/portal/llms-pages/http"
    endpoint = (portal / "api-endpoints/candidate-agent/respond-to-testah.md").read_text(encoding="utf-8")
    minimal = json.loads(re.search(r"--data-raw '(.*?)'", endpoint, re.S).group(1))
    guide = (portal / "candidate-integration/overview.md").read_text(encoding="utf-8")
    full = json.loads(re.search(r"```json\n(.*?)\n```", guide, re.S).group(1))
    monkeypatch.delenv("TESTAH_SAMPLE_TOKEN", raising=False)
    with TestClient(app) as client:
        for request, expected in ((minimal, "message"), (full, "tool_call")):
            AgentRequest.model_validate(request)
            response = client.post("/agent", json=request)
            assert response.status_code == 200
            assert response_adapter.validate_python(response.json()).type == expected
    page = (portal / "models/oneof-anyof-definitions/agent-response.md").read_text(encoding="utf-8")
    examples = [response_adapter.validate_python(json.loads(raw)) for raw in re.findall(r"```bash\n(.*?)\n```", page, re.S)]
    assert {example.type for example in examples} == {"message", "tool_call", "completed"}
    call = next(example.tool_call for example in examples if example.type == "tool_call")
    assert call.name == "test_echo" and isinstance(call.arguments["text"], str)


@pytest.mark.parametrize("mutation", ["extra", "wrong_type", "wrong_version", "mixed_response"])
def test_documented_strict_response_boundary(mutation):
    response = copy.deepcopy(exporter.RESPONSE_EXAMPLES["message"])
    if mutation == "extra":
        response["internal_debug"] = "not allowed"
    elif mutation == "wrong_type":
        response["request_id"] = 123
    elif mutation == "wrong_version":
        response["protocol_version"] = "2.0"
    else:
        response["summary"] = "Cannot mix response variants"
    with pytest.raises(ValidationError):
        response_adapter.validate_python(response)
