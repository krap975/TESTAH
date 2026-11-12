import pytest
import logging
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def capture_rai_logs(caplog):
    # Embedded Uvicorn test servers configure non-propagating parent loggers.
    # Capture this operational logger directly and restore its state afterward.
    logger = logging.getLogger("uvicorn.error.rai")
    propagated = logger.propagate
    logger.propagate = False
    logger.addHandler(caplog.handler)
    try:
        yield
    finally:
        logger.removeHandler(caplog.handler)
        logger.propagate = propagated

@pytest.fixture
def client():
    settings = Settings(_env_file=None, database_url="sqlite:///:memory:")
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


from alembic import command
from alembic.config import Config
from pathlib import Path

@pytest.fixture
def agent_client(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "agents.db").as_posix()
    monkeypatch.setenv("TESTAH_DATABASE_URL", url)
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    settings = Settings(_env_file=None, database_url=url)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client
