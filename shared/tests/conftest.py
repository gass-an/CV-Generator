import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from cv_generator_shared.database import Base
from cv_generator_shared.models import ApiClient, ApiKey

SHARED_TABLES = [ApiClient.__table__, ApiKey.__table__]


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL n'est pas définie")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_test"
    ):
        pytest.fail(
            "TEST_DATABASE_URL doit désigner une base PostgreSQL suffixée _test"
        )

    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.drop_all(
                sync_connection, tables=SHARED_TABLES
            )
        )
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection, tables=SHARED_TABLES
            )
        )
    async with AsyncSession(engine, expire_on_commit=False) as test_session:
        yield test_session
        await test_session.rollback()
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.drop_all(
                sync_connection, tables=SHARED_TABLES
            )
        )
    await engine.dispose()
