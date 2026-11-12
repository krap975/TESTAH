from collections.abc import Generator
from pathlib import Path

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import BACKEND_ROOT


def build_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    options = {}
    if url.drivername in {"postgres", "postgresql"}:
        # Render supplies a standard URL; select our installed driver.
        url = url.set(drivername="postgresql+psycopg")
    if url.get_backend_name() == "postgresql":
        options["pool_pre_ping"] = True
        # Existing execution timestamps are UTC; do not reinterpret server-local offsets.
        options["connect_args"] = {"options": "-c timezone=UTC"}
    if url.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False}
        if url.database in (None, "", ":memory:"):
            options["poolclass"] = StaticPool
        elif not Path(url.database).is_absolute():
            url = url.set(database=str(BACKEND_ROOT / url.database))
    engine = create_engine(url, **options)
    if url.get_backend_name() == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
