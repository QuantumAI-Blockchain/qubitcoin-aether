"""Alembic migration environment for Qubitcoin.

Loads the database URL from the DATABASE_URL environment variable
(via dotenv), falling back to the value in alembic.ini.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Add project root to path so we can import qubitcoin modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env files (same order as config.py: secure_key.env first, then .env)
try:
    from dotenv import load_dotenv

    env_path = os.path.join(os.path.dirname(__file__), "..")
    load_dotenv(os.path.join(env_path, "secure_key.env"), override=False)
    load_dotenv(os.path.join(env_path, ".env"), override=False)
except ImportError:
    pass

# Alembic Config object
config = context.config

# Override sqlalchemy.url from environment if available
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Set up loggers from config file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support.
# Qubitcoin currently uses dataclasses (not SQLAlchemy ORM models),
# so autogenerate is not available. Migrations must be written manually.
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Emits SQL to stdout without connecting to the database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Connects to the database and runs migrations within a transaction.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
