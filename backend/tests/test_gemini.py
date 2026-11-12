"""Credential-free Gemini transport and existing Phase 5 boundary verification."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import BACKEND_ROOT, Settings
from app.environments.designed import compile_design
from app.environments.runtime import initial_state
from app.rai import provider as module
from app.rai.designer import designer_manifest
from app.rai.examiner import generate_message, public_context
from app.rai.prompts import DESIGNER_PROMPT, EXAMINER_PROMPT
from app.rai.provider import GeminiProvider, MockProvider, OpenAIProvider, ProviderError, get_provider, provider_config
from app.schemas.environment_design import EnvironmentDesign
from app.schemas.rai import ExaminerPlan


def settings(**updates):
    return Settings(_env_file=None, **{"rai_provider": "gemini", "rai_model": "gemini-2.5-flash",
                    "rai_api_key": SecretStr("unit-test-gemini-key"), **updates})


@pytest.fixture
def public_dns(monkeypatch):
    seen = []
    async def resolve(host):
        seen.append(host)
        return "93.184.216.34"
    monkeypatch.setattr(module, "resolve_public", resolve)
    return seen


def plan():
    return {"version": "1.0", "intent": "clarify_budget", "tone": "concise",
            "preference_indexes": [], "challenge_request": None}


def envelope(value):
    return {"candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [
        {"thought": True, "text": "Private reasoning never persisted"}, {"text": json.dumps(value)}]}}]}


def wire(body, status=200, headers=None):
    return httpx.Response(status, headers={"content-type": "application/json", **(headers or {})},
                          stream=httpx.ByteStream(json.dumps(body).encode()))


def generate(adapter):
    return asyncio.run(adapter.generate("examiner", EXAMINER_PROMPT, {}, ExaminerPlan.model_json_schema()))


def test_gemini_contract_for_designer_and_examiner(public_dns):
    manifest = designer_manifest({"declared_description": "Commerce shopping", "commerce_evidence": True})
    design = asyncio.run(MockProvider().generate("designer", DESIGNER_PROMPT, manifest, {}))
    design["name"] = "Synthetic provider contract proposal"
    seen = []
    def handler(request):
        seen.append(request)
        assert request.url.host == "93.184.216.34"
        assert request.url.path == "/v1beta/models/gemini-2.5-flash:generateContent"
        assert not request.url.query
        assert request.headers["host"] == "generativelanguage.googleapis.com"
        assert request.extensions["sni_hostname"] == "generativelanguage.googleapis.com"
        assert request.headers["x-goog-api-key"] == "unit-test-gemini-key"
        body = json.loads(request.content)
        assert "tools" not in body and "unit-test-gemini-key" not in request.content.decode()
        generation = body["generationConfig"]
        assert generation["maxOutputTokens"] == 3000 and generation["candidateCount"] == 1
        assert generation["responseMimeType"] == "application/json"
        assert generation["responseJsonSchema"]["additionalProperties"] is False
        assert generation["thinkingConfig"] == {"thinkingBudget": 0, "includeThoughts": False}
        assert "untrusted_data" in body["contents"][0]["parts"][0]["text"]
        instructions = body["systemInstruction"]["parts"][0]["text"]
        assert instructions == (DESIGNER_PROMPT if len(seen) == 1 else EXAMINER_PROMPT)
        return wire(envelope(design if len(seen) == 1 else plan()))
    adapter = GeminiProvider(settings(), httpx.MockTransport(handler))
    output = asyncio.run(adapter.generate("designer", DESIGNER_PROMPT, manifest, EnvironmentDesign.model_json_schema()))
    blueprint = compile_design(EnvironmentDesign.model_validate(output), "gemini-contract")
    state = initial_state(blueprint); before = deepcopy(state)
    message, validated = asyncio.run(generate_message(adapter, public_context(blueprint, state, [])))
    assert validated.intent == "clarify_budget" and "Messages never approve purchases" in message
    assert state == before
    assert len(seen) == 2 and public_dns == ["generativelanguage.googleapis.com"] * 2


@pytest.mark.parametrize("key,model", [("", "gemini-2.5-flash"), ("REPLACE_WITH_YOUR_GEMINI_API_KEY", "gemini-2.5-flash"),
                                      ("test-key", ""), ("test-key", "configured-test-model"), ("bad\nkey", "gemini-2.5-flash")])
def test_gemini_missing_or_invalid_configuration_never_uses_network(public_dns, key, model):
    with pytest.raises(ProviderError) as error:
        generate(get_provider(settings(rai_api_key=SecretStr(key), rai_model=model)))
    assert error.value.code == "provider_not_configured" and public_dns == []


@pytest.mark.parametrize("status,code,attempts", [(401, "provider_authentication_failed", 1), (403, "provider_authentication_failed", 1),
    (404, "provider_model_unavailable", 1), (400, "provider_http_error", 1), (307, "provider_http_error", 1),
    (429, "provider_transient_error", 2), (503, "provider_transient_error", 2)])
def test_gemini_failures_are_safe_bounded_and_never_mock(public_dns, status, code, attempts):
    def handler(_request):
        return wire({"error": {"message": "private unit-test-gemini-key"}}, status,
                    {"location": "http://127.0.0.1/private"})
    with pytest.raises(ProviderError) as error:
        generate(GeminiProvider(settings(), httpx.MockTransport(handler)))
    assert error.value.code == code and len(public_dns) == attempts
    assert error.value.http_status == status
    assert "private" not in str(error.value) and "unit-test-gemini-key" not in str(error.value)


@pytest.mark.parametrize("problem,code", [("blocked", "provider_refusal"), ("safety", "provider_refusal"),
    ("truncated", "provider_incomplete"), ("bad_json", "invalid_model_output"), ("duplicate", "invalid_model_output"),
    ("nonfinite", "invalid_model_output"), ("multiple", "invalid_model_output"), ("no_text", "invalid_model_output"),
    ("tool", "invalid_model_output"), ("mime", "invalid_model_output"), ("compressed", "invalid_model_output"),
    ("size", "provider_response_too_large"), ("stream_size", "provider_response_too_large"),
    ("invalid_finish_reason", "invalid_model_output")])
def test_gemini_rejects_unusable_responses(public_dns, problem, code):
    body = envelope(plan()); candidate = body["candidates"][0]; headers = {}
    if problem == "blocked": body = {"promptFeedback": {"blockReason": "SAFETY"}}
    if problem == "safety": candidate["finishReason"] = "SAFETY"
    if problem == "truncated": candidate["finishReason"] = "MAX_TOKENS"
    if problem == "invalid_finish_reason": candidate["finishReason"] = ["STOP"]
    if problem in {"bad_json", "duplicate", "nonfinite"}:
        candidate["content"]["parts"][1]["text"] = {"bad_json": "not JSON", "duplicate": '{"a":1,"a":2}', "nonfinite": '{"a":NaN}'}[problem]
    if problem == "multiple": body["candidates"].append(deepcopy(candidate))
    if problem == "no_text": candidate["content"]["parts"] = []
    if problem == "tool": candidate["content"]["parts"] = [{"functionCall": {"name": "create_checkout"}}]
    if problem == "mime": headers["content-type"] = "text/html"
    if problem == "compressed": headers["content-encoding"] = "gzip"
    if problem == "size": headers["content-length"] = "999999999"
    if problem == "stream_size": body["padding"] = "x" * 140000
    with pytest.raises(ProviderError) as error:
        generate(GeminiProvider(settings(), httpx.MockTransport(lambda _: wire(body, headers=headers))))
    assert error.value.code == code and len(public_dns) == 1


def test_gemini_accepts_split_text_parts():
    body = envelope(plan())
    content = json.dumps(plan())
    body["candidates"][0]["content"]["parts"] = [{"text": content[:15]}, {"text": content[15:]}]
    assert GeminiProvider(settings()).parse_response(body) == plan()


@pytest.mark.parametrize("failure,code", [(httpx.ConnectError("private"), "provider_unreachable"),
                                         (httpx.ReadTimeout("private"), "provider_timeout")])
def test_gemini_network_failures(public_dns, failure, code):
    def handler(_request): raise failure
    with pytest.raises(ProviderError) as error:
        generate(GeminiProvider(settings(), httpx.MockTransport(handler)))
    assert error.value.code == code and len(public_dns) == 2


def test_gemini_total_timeout(public_dns):
    async def slow(_request): await asyncio.sleep(2)
    with pytest.raises(ProviderError) as error:
        generate(GeminiProvider(settings(rai_timeout_seconds=1, rai_retries=0), httpx.MockTransport(slow)))
    assert error.value.code == "provider_timeout"


def test_retry_capacity_does_not_cut_generation_deadline_in_half(public_dns):
    calls = []
    async def slow_valid(request):
        calls.append(request)
        # Above the previous 0.5-second attempt limit, below the 1-second total.
        await asyncio.sleep(.6)
        return wire(envelope(plan()))
    assert generate(GeminiProvider(settings(rai_timeout_seconds=1, rai_retries=1), httpx.MockTransport(slow_valid))) == plan()
    assert len(calls) == 1 and len(public_dns) == 1


def test_gemini_35_flash_lite_request_uses_supported_structured_settings(public_dns):
    def handler(request):
        assert request.url.path == "/v1beta/models/gemini-3.5-flash-lite:generateContent"
        generation = json.loads(request.content)["generationConfig"]
        assert generation["responseMimeType"] == "application/json"
        assert generation["responseJsonSchema"]["additionalProperties"] is False
        assert "thinkingConfig" not in generation
        return wire(envelope(plan()))
    assert generate(GeminiProvider(settings(rai_model="gemini-3.5-flash-lite"), httpx.MockTransport(handler))) == plan()


def test_gemini_schema_limits_decoding_cost_without_changing_validation():
    from app.rai.provider import gemini_json_schema
    original = EnvironmentDesign.model_json_schema(); before = deepcopy(original)
    wire_schema = gemini_json_schema(original)
    assert original == before
    def inspect(node):
        if isinstance(node, dict):
            assert not ({"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength", "minItems", "maxItems", "pattern"} & node.keys())
            if node.get("type") == "object":
                assert node["additionalProperties"] is False and set(node["required"]) == set(node["properties"])
            for value in node.values(): inspect(value)
        elif isinstance(node, list):
            for value in node: inspect(value)
    inspect(wire_schema)
    budget = wire_schema["properties"]["budget_minor"]
    assert budget["type"] == "integer" and "maximum=1000000" in budget["description"]
    assert original["properties"]["budget_minor"]["maximum"] == 1_000_000
    data = asyncio.run(MockProvider().generate("designer", DESIGNER_PROMPT, designer_manifest({"declared_description": "Commerce", "commerce_evidence": True}), {}))
    for invalid_budget in (0, 1_000_001, True, 1000.5):
        with pytest.raises(ValidationError): EnvironmentDesign.model_validate({**data, "budget_minor": invalid_budget})


@pytest.mark.parametrize("exception,code", [(httpx.RemoteProtocolError("unit-test-gemini-key"), "provider_protocol_error"),
    (httpx.DecodingError("unit-test-gemini-key"), "invalid_model_output"),
    (httpx.ProxyError("unit-test-gemini-key"), "provider_proxy_error")])
def test_nonnetwork_transport_errors_are_not_unreachable(public_dns, exception, code, caplog):
    def handler(_request): raise exception
    with pytest.raises(ProviderError) as error:
        generate(GeminiProvider(settings(), httpx.MockTransport(handler)))
    assert error.value.code == code and len(public_dns) == 1
    assert "unit-test-gemini-key" not in caplog.text and code in caplog.text


def test_http_status_exception_is_not_unreachable(public_dns, caplog):
    def handler(request):
        raise httpx.HTTPStatusError("unit-test-gemini-key", request=request, response=httpx.Response(400))
    with pytest.raises(ProviderError) as error:
        generate(GeminiProvider(settings(), httpx.MockTransport(handler)))
    assert error.value.code == "provider_http_error" and error.value.http_status == 400
    assert "http_status=400" in caplog.text and "unit-test-gemini-key" not in caplog.text


def test_socket_permission_denial_is_not_retried(public_dns):
    def handler(_request):
        try: raise PermissionError("unit-test-gemini-key")
        except PermissionError as exc: raise httpx.ConnectError("private") from exc
    with pytest.raises(ProviderError) as error:
        generate(GeminiProvider(settings(), httpx.MockTransport(handler)))
    assert error.value.code == "provider_network_denied" and len(public_dns) == 1


@pytest.mark.parametrize("reason,code", [("dns_error", "provider_dns_error"), ("destination_blocked", "provider_destination_blocked")])
def test_dns_failure_is_distinct_from_destination_policy(monkeypatch, reason, code):
    from app.execution.network import DestinationError
    async def blocked(_host): raise DestinationError(reason)
    monkeypatch.setattr(module, "resolve_public", blocked)
    with pytest.raises(ProviderError) as error: generate(GeminiProvider(settings()))
    assert error.value.code == code


def test_explicit_provider_selection_and_frozen_config():
    configured = settings()
    assert isinstance(get_provider(configured), GeminiProvider)
    assert isinstance(get_provider(configured, {"rai_provider": "mock"}), MockProvider)
    assert isinstance(get_provider(configured, {"rai_provider": "openai"}), OpenAIProvider)
    with pytest.raises(ProviderError): get_provider(configured, {"rai_provider": "unknown"})
    assert "rai_api_key" not in provider_config(configured)


def test_settings_load_absolute_env_from_other_working_directory(tmp_path, monkeypatch):
    for name in list(os.environ):
        if name.startswith("TESTAH_"): monkeypatch.delenv(name)
    assert Settings.model_config["env_file"] == BACKEND_ROOT / ".env"
    env = tmp_path / "backend.env"
    env.write_text('TESTAH_APP_NAME=Testah API\nTESTAH_DATABASE_URL=sqlite:///./testah.db\n'
                   'TESTAH_CORS_ORIGINS=["http://localhost:5173"]\nTESTAH_RAI_PROVIDER=gemini\n'
                   'TESTAH_RAI_MODEL=gemini-2.5-flash\nTESTAH_RAI_API_KEY=unit-test-key\n', encoding="utf-8")
    monkeypatch.setitem(Settings.model_config, "env_file", env)
    elsewhere = tmp_path / "elsewhere"; elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    loaded = Settings()
    assert Path(loaded.model_config["env_file"]) == env
    assert loaded.app_name == "Testah API" and loaded.database_url == "sqlite:///./testah.db"
    assert loaded.cors_origins == ["http://localhost:5173"]
    assert loaded.rai_provider == "gemini" and loaded.rai_model == "gemini-2.5-flash"
    assert loaded.rai_api_key.get_secret_value() == "unit-test-key"
    assert loaded.rai_api_key.get_secret_value() not in repr(loaded)
    monkeypatch.setenv("TESTAH_RAI_PROVIDER", "mock")
    assert Settings().rai_provider == "mock"


def test_settings_env_names_and_limits(tmp_path, monkeypatch):
    monkeypatch.setenv("TESTAH_RAI_PROVIDER", "gemini")
    monkeypatch.setenv("TESTAH_RAI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("TESTAH_RAI_API_KEY", "unit-test-key")
    env = tmp_path / "settings.env"
    env.write_text("TESTAH_RAI_TIMEOUT_SECONDS=30\nTESTAH_RAI_MAX_OUTPUT_TOKENS=3000\nTESTAH_RAI_MAX_RESPONSE_BYTES=131072\n", encoding="utf-8")
    loaded = Settings(_env_file=env)
    assert loaded.rai_provider == "gemini" and loaded.rai_timeout_seconds == 30
    assert loaded.rai_model == "gemini-2.5-flash" and loaded.rai_api_key.get_secret_value() == "unit-test-key"
    assert loaded.rai_max_output_tokens == 3000 and loaded.rai_max_response_bytes == 131072
    with pytest.raises(ValidationError): Settings(_env_file=None, rai_max_output_tokens=8001)
