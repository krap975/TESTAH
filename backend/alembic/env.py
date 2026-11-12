from alembic import context
from sqlalchemy.engine import Connection
from app.core.config import Settings
from app.database.session import build_engine
from app.models import Base

config = context.config
target_metadata = Base.metadata


def run_online(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


supplied_connection = config.attributes.get("connection")
if supplied_connection is not None:
    # The Render launcher holds its PostgreSQL migration lock on this connection.
    run_online(supplied_connection)
else:
    engine = build_engine(Settings().database_url)
    try:
        if context.is_offline_mode():
            context.configure(url=engine.url, target_metadata=target_metadata, literal_binds=True)
            with context.begin_transaction():
                context.run_migrations()
        else:
            with engine.connect() as connection:
                run_online(connection)
    finally:
        engine.dispose()
