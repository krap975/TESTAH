import asyncio
from copy import deepcopy
import json
import httpx
import pytest
from pydantic import SecretStr
from app.core.config import Settings
from app.rai import provider as module
from app.rai.designer import designer_manifest
from app.rai.prompts import DESIGNER_PROMPT, EXAMINER_PROMPT
from app.rai.provider import MockProvider, OpenAIProvider, ProviderError, parse_json, strict_json_schema, secret_values
from app.events.store import sanitize
from app.schemas.environment_design import EnvironmentDesign
from app.schemas.rai import ExaminerPlan


def settings(**updates):
    return Settings(_env_file=None, rai_provider="openai", rai_model="configured-test-model", rai_api_key=SecretStr("unit-test-key"), **updates)


@pytest.fixture
def public_dns(monkeypatch):
    seen = []
    async def resolve(host):
        seen.append(host)
        return "93.184.216.34"
    monkeypatch.setattr(module, "resolve_public", resolve)
    return seen


def wire(envelope, status=200, headers=None):
    return httpx.Response(status, headers={"content-type": "application/json", **(headers or {})},
                          stream=httpx.ByteStream(json.dumps(envelope).encode()))


def envelope(value):
    return {"status": "completed", "output": [{"type": "reasoning", "summary": [{"text": "Never persist hidden reasoning"}]},
              {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": json.dumps(value)}]}]}


def generate(adapter):
    return asyncio.run(adapter.generate("examiner", EXAMINER_PROMPT, {"candidate_question": "Budget?"}, ExaminerPlan.model_json_schema()))


def test_openai_adapter_contract_and_pinning(public_dns):
    plan = {"version": "1.0", "intent": "clarify_budget", "tone": "concise", "preference_indexes": [], "challenge_request": None}
    seen = []
    def handler(request):
        seen.append(request)
        assert request.url.host == "93.184.216.34" and request.url.path == "/v1/responses"
        assert request.headers["host"] == "api.openai.com" and request.extensions["sni_hostname"] == "api.openai.com"
        assert request.headers["authorization"] == "Bearer unit-test-key"
        body = json.loads(request.content)
        assert body["store"] is False and body["max_output_tokens"] == 3000
        assert body["model"] == "configured-test-model" and "tools" not in body
        assert "untrusted_data" in body["input"][0]["content"]
        assert body["text"]["format"]["strict"] is True
        assert body["text"]["format"]["schema"]["additionalProperties"] is False
        return wire(envelope(plan))
    assert generate(OpenAIProvider(settings(), httpx.MockTransport(handler))) == plan
    assert len(seen) == 1 and public_dns == ["api.openai.com"]


@pytest.mark.parametrize("status,expected", [(429, 2), (500, 2), (503, 2), (400, 1), (401, 1), (403, 1), (307, 1)])
def test_only_transient_provider_posts_retry(public_dns, status, expected):
    attempts = []
    def handler(request):
        attempts.append(request)
        return wire({"private": "unit-test-key"}, status, {"location": "http://127.0.0.1/private"})
    with pytest.raises(ProviderError) as error:
        generate(OpenAIProvider(settings(), httpx.MockTransport(handler)))
    assert error.value.code in {"provider_transient_error", "provider_http_error"}
    assert len(attempts) == expected and len(public_dns) == expected
    assert "unit-test-key" not in str(error.value)


@pytest.mark.parametrize("problem,code", [
    ("incomplete", "provider_incomplete"), ("refusal", "provider_refusal"), ("wrong_json", "invalid_model_output"),
    ("extra_output", "invalid_model_output"), ("content_type", "invalid_model_output"),
    ("compressed", "invalid_model_output"), ("size", "provider_response_too_large"),
])
def test_provider_rejects_unusable_outputs(public_dns, problem, code):
    body = envelope({"version": "1.0"}); headers = {}
    if problem == "incomplete": body["status"] = "incomplete"
    if problem == "refusal": body["output"][1]["content"] = [{"type": "refusal", "refusal": "private reason"}]
    if problem == "wrong_json": body["output"][1]["content"][0]["text"] = "{not json"
    if problem == "extra_output": body["output"][1]["content"].append({"type": "output_text", "text": "{}"})
    if problem == "content_type": headers["content-type"] = "text/html"
    if problem == "compressed": headers["content-encoding"] = "gzip"
    if problem == "size": headers["content-length"] = "999999999"
    with pytest.raises(ProviderError) as error:
        generate(OpenAIProvider(settings(), httpx.MockTransport(lambda _: wire(body, headers=headers))))
    assert error.value.code == code
    assert len(public_dns) == 1


@pytest.mark.parametrize("exception,code", [(httpx.ReadTimeout("private"), "provider_timeout"), (httpx.ConnectError("private"), "provider_unreachable")])
def test_provider_network_failure_bounded(public_dns, exception, code):
    seen = []
    def handler(request):
        seen.append(request)
        raise exception
    with pytest.raises(ProviderError) as error:
        generate(OpenAIProvider(settings(), httpx.MockTransport(handler)))
    assert len(seen) == 2 and error.value.code == code


def test_provider_total_timeout(public_dns):
    async def slow(_request):
        await asyncio.sleep(2)
    with pytest.raises(ProviderError) as error:
        generate(OpenAIProvider(settings(rai_timeout_seconds=1, rai_retries=0), httpx.MockTransport(slow)))
    assert error.value.code == "provider_timeout"


def test_missing_credentials_fail_before_network(public_dns):
    with pytest.raises(ProviderError) as error:
        generate(OpenAIProvider(Settings(_env_file=None, rai_provider="openai")))
    assert error.value.code == "provider_not_configured" and not public_dns


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '[]', 'null', 'not JSON'])
def test_strict_json_parsing(text):
    with pytest.raises(ProviderError):
        parse_json(text)


def test_structured_schema_requires_every_field_without_mutating_source():
    schema = EnvironmentDesign.model_json_schema(); original = deepcopy(schema)
    strict = strict_json_schema(schema)
    assert schema == original
    def check(node):
        if isinstance(node, dict):
            assert "default" not in node
            if node.get("type") == "object":
                assert set(node["required"]) == set(node["properties"]) and node["additionalProperties"] is False
            for child in node.values(): check(child)
        elif isinstance(node, list):
            for child in node: check(child)
    check(strict)


def test_mock_provider_is_deterministic_and_validated():
    manifest = designer_manifest({"declared_description": "Commerce with shipping and price changes", "commerce_evidence": True})
    async def twice():
        mock = MockProvider()
        return await mock.generate("designer", DESIGNER_PROMPT, manifest, {}), await mock.generate("designer", DESIGNER_PROMPT, manifest, {})
    one, two = asyncio.run(twice())
    assert one == two and "Mock" in one["name"] and one["template_id"] == "price_change_before_checkout"
    assert EnvironmentDesign.model_validate(one).customer.synthetic


def test_redaction_includes_bare_credentials_from_complete_headers():
    configured = Settings(_env_file=None, rai_api_key=SecretStr("provider-private-key"), agent_secrets={
        "CANDIDATE": SecretStr("  Bearer   candidate-private-token  "), "BASIC": SecretStr("Basic private-base64-value")})
    cleaned = sanitize({"question": "Echo candidate-private-token private-base64-value provider-private-key"}, secret_values(configured))
    assert all(value not in cleaned["question"] for value in ("candidate-private-token", "private-base64-value", "provider-private-key"))
