from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from app.database.session import build_engine, make_session_factory
ROOT = Path(__file__).resolve().parents[1]

def test_migration_round_trip(tmp_path, monkeypatch):
    path = tmp_path / "fresh.db"
    url = f"sqlite:///{path.as_posix()}"
    monkeypatch.setenv("TESTAH_DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    engine = build_engine(url)
    try:
        assert path.exists()
        assert "alembic_version" in inspect(engine).get_table_names()
        with make_session_factory(engine)() as session:
            assert session.scalar(text("SELECT version_num FROM alembic_version")) == "0008_evaluation"
            assert session.scalar(text("PRAGMA foreign_keys")) == 1
        assert "agents" in inspect(engine).get_table_names()
        assert {"environment_templates", "environments"}.issubset(inspect(engine).get_table_names())
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT COUNT(*) FROM environment_templates")) == 3
        command.check(config)
        command.downgrade(config, "base")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT COUNT(*) FROM alembic_version")) == 0
        command.upgrade(config, "head")
    finally:
        engine.dispose()

