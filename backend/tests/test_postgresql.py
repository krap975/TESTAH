"""Opt-in disposable PostgreSQL contract; also run by GitHub CI.

TESTAH_TEST_POSTGRES_URL must name a NEW EMPTY test database. Never point at saved data.
"""
import os
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from app.core.config import Settings
from app.database.session import build_engine, make_session_factory
from app.main import create_app
from app.models.agent import Agent
from app.models.assessment import Assessment
from app.execution.service import start_assessment, locked_run, cancel_assessment
from app.events.store import append_event

URL = os.environ.get("TESTAH_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="No disposable PostgreSQL URL configured")


def test_postgresql_migrations_transactions_and_persistence(monkeypatch):
    engine = build_engine(URL)
    # Refuse to touch a database containing application tables.
    assert not inspect(engine).get_table_names(), "PostgreSQL test requires a new empty database."
    monkeypatch.setenv("TESTAH_DATABASE_URL", URL)
    monkeypatch.setenv("TESTAH_ENVIRONMENT", "test")
    monkeypatch.setenv("TESTAH_ALLOW_LOCAL_SAMPLE", "false")
    monkeypatch.setenv("TESTAH_RAI_PROVIDER", "mock")
    monkeypatch.setenv("TESTAH_PAYMENT_MODE", "simulated")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SHOW timezone")) == "UTC"
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        command.check(config)
        assert set(inspect(engine).get_table_names()) >= {"agents", "payments", "run_events", "evaluations"}
        # Exercise real JSON, timestamp, constraints, transactions and event sequencing.
        settings = Settings(_env_file=None, database_url=URL, environment="test")
        with TestClient(create_app(settings)) as client:
            assert client.get("/api/health").status_code == 200
            agent = client.post("/api/agents", json={"name": "Postgres sample", "endpoint_url": "https://example.com/agent"}).json()
            with client.app.state.session_factory() as session, session.begin():
                session.get(Agent, agent["id"]).last_test_status = "connected"
            env = client.post("/api/environments", json={"name": "Postgres environment", "template_id": "price_change_before_checkout"}).json()
            run_response = client.post("/api/assessments", json={"agent_id": agent["id"], "environment_id": env["id"]})
            assert run_response.status_code == 201, run_response.text
            run = run_response.json()
            factory = client.app.state.session_factory
            _, claim = start_assessment(factory, run["id"], settings)
            with locked_run(factory, run["id"], claim) as (session, record):
                append_event(session, record, "test.postgres", {"value": "persisted"})
            cancel_assessment(factory, run["id"])
            assert client.get("/api/assessments/" + run["id"]).json()["status"] == "cancelled"
        # A fresh application/engine reads committed state after restart.
        with TestClient(create_app(settings)) as restarted:
            assert restarted.get("/api/agents/" + agent["id"]).status_code == 200
            assert restarted.get("/api/assessments/" + run["id"]).json()["status"] == "cancelled"
        with make_session_factory(engine)() as session:
            assert session.scalar(select(Assessment.id).where(Assessment.id == run["id"])) == run["id"]
        command.downgrade(config, "base")
        assert inspect(engine).get_table_names() == ["alembic_version"]
        command.upgrade(config, "head")
        command.check(config)
    finally:
        engine.dispose()
