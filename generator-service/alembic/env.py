import asyncio
from logging.config import fileConfig

from alembic import context
from app.core.config import get_settings
from app.core.database import Base
from app.models import DocumentJob  # noqa: F401
from cv_generator_shared.admin_models import (  # noqa: F401
    AdminLoginAttempt,
    AdminSession,
)
from cv_generator_shared.models import ApiClient, ApiKey  # noqa: F401
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option(
    "sqlalchemy.url",
    get_settings().database_url.replace("%", "%%"),
)
target_metadata = Base.metadata


def do_run_migrations(connection: object) -> None:
    """Configure Alembic et exécute les migrations sur une connexion synchrone."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Ouvre le moteur async puis délègue l'exécution synchrone à Alembic."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Lance les migrations en ligne dans une boucle asyncio dédiée."""
    asyncio.run(run_async_migrations())


run_migrations_online()
