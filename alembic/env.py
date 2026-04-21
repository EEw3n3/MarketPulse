"""
Alembic env.py — async SQLModel + asyncpg setup.
Reads DATABASE_URL from .env via app.core.config.settings.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from alembic import context
from sqlmodel import SQLModel

# Import all models so their metadata is registered
from app.domain.models import (  # noqa: F401
    Product, ProductGroup, ScrapingRule, PriceHistory, SharedPattern,
    User, UserPreferences,
)
from app.core.config import settings

# Alembic Config object
config = context.config

# Set DB URL from our settings (reads .env automatically)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Setup logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLModel metadata — autogenerate will compare this against the live DB
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Offline mode: generate SQL script without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # detect column type changes
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Online mode: use asyncpg engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
