"""Render entry point: migrate a new PostgreSQL database, then serve one worker."""
import os
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from alembic import command
from alembic.config import Config
from sqlalchemy import text
import uvicorn
from app.core.config import Settings
from app.database.session import build_engine

MIGRATION_LOCK = 742381905


def migrate(settings: Settings) -> None:
    engine = build_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            # A session-level lock serializes overlapping Render deploy migrations.
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK})
            connection.commit()
            try:
                config = Config(str(BACKEND_ROOT / "alembic.ini"))
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
            finally:
                connection.rollback()
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK})
                connection.commit()
    finally:
        engine.dispose()


def main() -> None:
    try:
        settings = Settings()
        if settings.environment != "production":
            raise ValueError("Render requires production settings.")
        port = int(os.environ["PORT"])
        if not 1 <= port <= 65535:
            raise ValueError("Invalid port.")
        migrate(settings)
    except Exception:
        # Connection exceptions/settings may contain private operational details.
        raise SystemExit("Render startup failed: check production settings, PORT and database migrations.") from None
    uvicorn.run("app.main:create_app", factory=True, host="0.0.0.0", port=port,
                workers=1, timeout_graceful_shutdown=5)


if __name__ == "__main__":
    main()
