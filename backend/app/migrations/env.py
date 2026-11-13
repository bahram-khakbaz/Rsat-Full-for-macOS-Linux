"""Alembic environment.

``app.db.init_db`` passes an open connection through ``config.attributes`` so
start-up migrations run in the application's own transaction. Running the
``alembic`` CLI (see ``backend/alembic.ini``) falls back to the configured engine.
"""

from alembic import context

from app.db import Base, engine

config = context.config
target_metadata = Base.metadata


def run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


supplied = config.attributes.get("connection")
if supplied is not None:
    run_migrations(supplied)
else:
    with engine.begin() as owned:
        run_migrations(owned)
