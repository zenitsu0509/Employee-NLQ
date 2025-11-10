from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.exc import OperationalError
from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# In this simple setup we don't use ORM metadata
# target_metadata = Base.metadata


def get_url() -> str:
    # Prefer VECTOR_DB_URL, else fall back to DATABASE_URL
    return os.getenv("VECTOR_DB_URL") or os.getenv("DATABASE_URL") or "postgresql+psycopg://user:pass@localhost:5432/embeddings"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Ensure the SQLAlchemy URL is set on the Alembic config before reading the section
    config.set_main_option("sqlalchemy.url", get_url())

    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=None)

            with context.begin_transaction():
                context.run_migrations()
    except OperationalError as exc:
        url = config.get_main_option("sqlalchemy.url")
        print(
            f"[alembic] Failed to connect using URL '{url}'.\n"
            "Set a valid DATABASE_URL or VECTOR_DB_URL environment variable before running migrations.\n"
            "Example: export DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/employee_nlq"
        )
        raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
