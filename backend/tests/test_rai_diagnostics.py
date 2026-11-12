import asyncio
import json
import logging
from pathlib import Path
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.main import create_app
from app.rai import provider as module
from app.rai.diagnostics import diagnostic_scope, timed_phase
from app.rai.provider import GeminiProvider, ProviderError

LOGGER = "uvicorn.error.rai"
pytestmark = pytest.mark.usefixtures("capture_rai_logs")


def records(caplog):
    return [json.loads(record.getMessage().split("RAI timing ", 1)[1]) for record in caplog.records
            if record.name == LOGGER and record.getMessage().startswith("RAI timing ")]


def configured(**updates):
    return Settings(_env_file=None, **{"rai_provider": "gemini", "rai_model": "gemini-3.5-flash-lite",
                    "rai_api_key": SecretStr("sensitive-test-provider-key"), **updates})


def test_startup_reports_actual_settings_and_restart_reloads_dotenv(tmp_path, monkeypatch, caplog):
    for name in ("TESTAH_RAI_PROVIDER", "TESTAH_RAI_MODEL", "TESTAH_RAI_API_KEY", "TESTAH_RAI_TIMEOUT_SECONDS", "TESTAH_RAI_GENERATION_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / ".env"
    env.write_text("TESTAH_RAI_TIMEOUT_SECONDS=30\nTESTAH_RAI_GENERATION_SECONDS=90\nTESTAH_RAI_API_KEY=sensitive-test-provider-key\n")
    initial = Settings(_env_file=env, database_url="sqlite:///:memory:")
    env.write_text("TESTAH_RAI_TIMEOUT_SECONDS=60\nTESTAH_RAI_GENERATION_SECONDS=180\nTESTAH_RAI_API_KEY=sensitive-test-provider-key\n")
    with caplog.at_level(logging.INFO, logger=LOGGER):
        with TestClient(create_app(initial)) as client:
            assert client.app.state.settings.rai_timeout_seconds == 30
            assert client.app.state.settings.rai_generation_seconds == 90
        with TestClient(create_app(Settings(_env_file=env, database_url="sqlite:///:memory:"))) as client:
            assert client.app.state.settings.rai_timeout_seconds == 60
            assert client.app.state.settings.rai_generation_seconds == 180
    configs = [json.loads(record.getMessage().split("RAI effective configuration ", 1)[1]) for record in caplog.records
               if record.getMessage().startswith("RAI effective configuration ")]
    assert [config["rai_timeout_seconds"] for config in configs] == [30, 60]
    assert "sensitive-test-provider-key" not in caplog.text
    monkeypatch.setenv("TESTAH_RAI_TIMEOUT_SECONDS", "45")
    assert Settings(_env_file=env).rai_timeout_seconds == 45
    with pytest.raises(ValidationError): configured(rai_timeout_seconds=61)
    with pytest.raises(ValidationError): configured(rai_generation_seconds=181)


def test_context_timing_is_isolated_and_does_not_log_exception_messages(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        with pytest.raises(ValueError), diagnostic_scope("safe-proposal-id"), timed_phase("schema_validation"):
            raise ValueError("sensitive-test-provider-key private input")
        with timed_phase("environment_compilation"):
            pass
    values = records(caplog)
    assert values[0]["proposal_id"] == "safe-proposal-id" and values[0]["exception_type"] == "ValueError"
    assert values[1]["proposal_id"] is None and values[1]["elapsed_ms"] >= 0
    assert "sensitive-test-provider-key" not in caplog.text and "private input" not in caplog.text


@pytest.mark.parametrize("httpx_timeout", [False, True])
def test_timing_distinguishes_httpx_timeout_from_total_deadline(monkeypatch, caplog, httpx_timeout):
    async def resolve(_host): return "93.184.216.34"
    monkeypatch.setattr(module, "resolve_public", resolve)
    async def handler(_request):
        if httpx_timeout: raise httpx.ReadTimeout("sensitive-test-provider-key")
        await asyncio.sleep(2)
    adapter = GeminiProvider(configured(rai_timeout_seconds=1, rai_retries=0), httpx.MockTransport(handler))
    with caplog.at_level(logging.INFO, logger=LOGGER), diagnostic_scope("timeout-proposal"):
        with pytest.raises(ProviderError) as error:
            asyncio.run(adapter.generate("designer", "private prompt", {"private": "input"}, {}))
    assert error.value.code == "provider_timeout"
    entries = records(caplog)
    timeout = next(entry for entry in entries if entry["phase"] == "provider_timeout")
    assert timeout["source"] == ("httpx" if httpx_timeout else "provider_deadline")
    assert "sensitive-test-provider-key" not in caplog.text and "private prompt" not in caplog.text


def test_retries_share_the_total_budget_and_report_time_spent(monkeypatch, caplog):
    async def resolve(_host): return "93.184.216.34"
    monkeypatch.setattr(module, "resolve_public", resolve)
    calls = []
    async def handler(_request):
        calls.append(1)
        await asyncio.sleep(.55)
        return httpx.Response(503)
    adapter = GeminiProvider(configured(rai_timeout_seconds=1, rai_retries=1), httpx.MockTransport(handler))
    start = time.monotonic()
    with caplog.at_level(logging.INFO, logger=LOGGER), pytest.raises(ProviderError) as error:
        asyncio.run(adapter.generate("designer", "private prompt", {}, {}))
    assert error.value.code == "provider_timeout" and len(calls) == 2
    assert time.monotonic() - start < 1.5
    entries = records(caplog)
    assert any(entry["phase"] == "provider_retry" and entry["next_attempt"] == 2 for entry in entries)
    assert any(entry["phase"] == "provider_timeout" and entry["source"] == "provider_deadline" for entry in entries)
