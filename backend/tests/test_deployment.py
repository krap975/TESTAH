"""Production boundary, origin validation and driver regression tests."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from app.core.config import Settings
from app.database.session import build_engine
from app.main import create_app

TOKEN = "test-workspace-" + "w" * 40


def production(**overrides):
    values = dict(_env_file=None, environment="production",
                  database_url="postgresql://test:test@localhost/test",
                  cors_origins=["https://demo.example.com"],
                  workspace_access_token=TOKEN)
    return Settings(**(values | overrides))


@pytest.mark.parametrize("values", [
    {"workspace_access_token": ""},
    {"database_url": "sqlite:///:memory:"},
    {"cors_origins": ["*"]}, {"cors_origins": []},
    {"cors_origins": ["http://demo.example.com"]},
    {"cors_origins": ["https://demo.example.com/"]},
    {"allow_local_sample": True},
    {"payment_mode": "paypal_sandbox"},
    {"monitor_token": TOKEN},
])
def test_production_fails_closed(values):
    with pytest.raises(ValidationError):
        production(**values)


@pytest.mark.parametrize("url", [
    "http://example.com", "http://localhost:8000", "https://localhost",
    "https://127.0.0.1", "https://10.0.0.1", "https://[::1]",
    "https://demo.internal", "https://x.local", "https://a.example/path",
    "https://a.example?state=private", "https://a.example#fragment",
    "https://name:private@a.example", "https://a.example:444",
    "https://a.example?", "https://a.example#",
])
def test_callback_rejects_unsafe_origins(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, paypal_callback_base_url=url)


def test_public_sandbox_callback_configuration():
    settings = production(payment_mode="paypal_sandbox", paypal_callback_base_url="https://api.example.com/")
    assert settings.paypal_callback_base_url == "https://api.example.com"
    assert settings.paypal_api_base_url == "https://api-m.sandbox.paypal.com"


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_postgres_driver_and_reconnect(scheme):
    engine = build_engine(scheme + "://test:test@localhost/test")
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.pool._pre_ping is True
    finally:
        engine.dispose()


def test_workspace_gate_and_existing_operator_authority(agent_client):
    client = agent_client
    # Reuse the isolated migrated DB, never the saved application database.
    settings = Settings(_env_file=None, database_url=str(client.app.state.engine.url),
                        workspace_access_token=TOKEN)
    with TestClient(create_app(settings), raise_server_exceptions=False) as secured:
        assert secured.get("/api/health").status_code == 200
        for path in ("/api/agents", "/api/environments", "/api/assessments", "/api/reports"):
            response = secured.get(path)
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "workspace_access_required"
        headers = {"X-Testah-Workspace-Token": TOKEN}
        assert secured.get("/api/agents", headers=headers).status_code == 200
        assert secured.get("/api/agents", headers={"X-Testah-Workspace-Token": "wrong"}).status_code == 401
        # The outer token grants neither payment nor monitor operator authority.
        assert secured.get("/api/assessments/missing/payments", headers=headers).status_code == 503
        assert secured.get("/api/assessments/missing/stream", headers=headers).status_code == 503
        # Missing callback capability still fails the existing route validation.
        callback = secured.get("/api/payments/return/missing/missing")
        assert callback.status_code == 422
        preflight = secured.options("/api/agents", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Testah-Workspace-Token",
        })
        assert preflight.status_code == 200
        assert secured.get("/api/agents", headers={"Origin": "http://localhost:5173"}).headers["access-control-allow-origin"] == "http://localhost:5173"


def test_production_hides_operator_docs_and_diagnostics():
    with TestClient(create_app(production()), raise_server_exceptions=False) as client:
        for path in ("/docs", "/redoc", "/openapi.json", "/api/rai/diagnostics"):
            assert client.get(path, headers={"X-Testah-Workspace-Token": TOKEN}).status_code == 404


def test_render_launcher_binds_assigned_port(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts/start_render.py"
    spec = importlib.util.spec_from_file_location("testah_render_start", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    settings = production()
    monkeypatch.setattr(module, "Settings", lambda: settings)
    migrate = Mock()
    serve = Mock()
    monkeypatch.setattr(module, "migrate", migrate)
    monkeypatch.setattr(module.uvicorn, "run", serve)
    monkeypatch.setenv("PORT", "10000")
    module.main()
    migrate.assert_called_once_with(settings)
    assert serve.call_args.kwargs["host"] == "0.0.0.0"
    assert serve.call_args.kwargs["port"] == 10000
    assert serve.call_args.kwargs["workers"] == 1
    migrate.side_effect = RuntimeError("private database information")
    with pytest.raises(SystemExit) as error:
        module.main()
    assert "private" not in str(error.value)
    assert serve.call_count == 1

def test_workspace_token_is_redacted_from_public_evidence():
    from app.events.public import public_event
    from app.models.agent import utcnow
    from app.models.assessment import RunEvent
    settings = Settings(_env_file=None, workspace_access_token=TOKEN)
    event = RunEvent(id="synthetic-event", run_id="synthetic-run", sequence=1,
                     event_type="test.recorded", created_at=utcnow(),
                     correlation_id=TOKEN, payload={"message": TOKEN})
    assert TOKEN not in public_event(event, settings).model_dump_json()
