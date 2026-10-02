import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Uuid, bindparam, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

SERVICE_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DOCUMENT_COLUMNS = {
    "id",
    "document_type",
    "status",
    "avp_number",
    "resume_data",
    "result_content",
    "result_format",
    "error_code",
    "error_message",
    "created_at",
    "started_at",
    "completed_at",
    "updated_at",
}
DOCUMENT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")


def _migration_database_url() -> str:
    database_url = os.getenv("MIGRATION_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("MIGRATION_TEST_DATABASE_URL n'est pas définie")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_migration_test"
    ):
        pytest.fail(
            "MIGRATION_TEST_DATABASE_URL doit désigner une base PostgreSQL "
            "suffixée _migration_test"
        )
    for variable_name in ("DATABASE_URL", "TEST_DATABASE_URL"):
        other_database_url = os.getenv(variable_name)
        if other_database_url is None:
            continue
        other_url = make_url(other_database_url)
        if other_url == url or other_url.database == url.database:
            pytest.fail(
                f"MIGRATION_TEST_DATABASE_URL doit être distincte de {variable_name}"
            )
    return database_url


def _run_alembic(database_url: str, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=SERVICE_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


async def _schema(database_url: str) -> dict[str, Any]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:

            def inspect_schema(sync_connection: object) -> dict[str, Any]:
                inspector = inspect(sync_connection)
                tables = set(inspector.get_table_names())
                document_columns = {
                    column["name"] for column in inspector.get_columns("document_job")
                }
                return {
                    "tables": tables,
                    "document_columns": document_columns,
                    "document_foreign_keys": {
                        (
                            tuple(item["constrained_columns"]),
                            item["referred_table"],
                            tuple(item["referred_columns"]),
                        )
                        for item in inspector.get_foreign_keys("document_job")
                    },
                    "document_indexes": {
                        item["name"] for item in inspector.get_indexes("document_job")
                    },
                    "api_client_checks": {
                        item["name"]
                        for item in inspector.get_check_constraints("api_client")
                    }
                    if "api_client" in tables
                    else set(),
                    "api_key_checks": {
                        item["name"]
                        for item in inspector.get_check_constraints("api_key")
                    }
                    if "api_key" in tables
                    else set(),
                    "api_key_uniques": {
                        item["name"]
                        for item in inspector.get_unique_constraints("api_key")
                    }
                    if "api_key" in tables
                    else set(),
                    "api_key_indexes": {
                        item["name"] for item in inspector.get_indexes("api_key")
                    }
                    if "api_key" in tables
                    else set(),
                    "api_key_foreign_keys": {
                        (
                            tuple(item["constrained_columns"]),
                            item["referred_table"],
                            tuple(item["referred_columns"]),
                        )
                        for item in inspector.get_foreign_keys("api_key")
                    }
                    if "api_key" in tables
                    else set(),
                }

            schema = await connection.run_sync(inspect_schema)
            schema["revision"] = (
                await connection.execute(
                    text("SELECT version_num FROM alembic_version")
                )
            ).scalar_one()
            schema["document_count"] = (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM document_job WHERE id = :document_id"
                    ).bindparams(bindparam("document_id", type_=Uuid(as_uuid=True))),
                    {"document_id": DOCUMENT_ID},
                )
            ).scalar_one()
            schema["document_client_id"] = (
                (
                    await connection.execute(
                        text(
                            "SELECT client_id FROM document_job WHERE id = :document_id"
                        ).bindparams(
                            bindparam("document_id", type_=Uuid(as_uuid=True))
                        ),
                        {"document_id": DOCUMENT_ID},
                    )
                ).scalar_one()
                if "client_id" in schema["document_columns"]
                else None
            )
            return schema
    finally:
        await engine.dispose()


def test_api_key_migration_upgrade_and_downgrade_on_isolated_postgresql() -> None:
    database_url = _migration_database_url()
    _run_alembic(database_url, "downgrade", "base")
    try:
        _run_alembic(database_url, "upgrade", "20260929_0002")
        asyncio.run(_insert_document(database_url))
        before = asyncio.run(_schema(database_url))
        assert before["revision"] == "20260929_0002"
        assert before["document_columns"] == EXPECTED_DOCUMENT_COLUMNS
        assert before["document_count"] == 1
        assert "api_client" not in before["tables"]
        assert "api_key" not in before["tables"]

        _run_alembic(database_url, "upgrade", "20261002_0003")
        upgraded = asyncio.run(_schema(database_url))
        assert upgraded["revision"] == "20261002_0003"
        assert upgraded["document_columns"] == before["document_columns"]
        assert upgraded["document_count"] == 1
        assert {"api_client", "api_key"} <= upgraded["tables"]
        assert upgraded["api_client_checks"] == {
            "ck_api_client_active_disabled_at",
            "ck_api_client_name_non_empty",
        }
        assert upgraded["api_key_checks"] == {
            "ck_api_key_expires_after_creation",
            "ck_api_key_name_non_empty",
            "ck_api_key_revoked_after_creation",
        }
        assert upgraded["api_key_uniques"] == {
            "uq_api_key_key_hash",
            "uq_api_key_prefix",
        }
        assert "ix_api_key_client_id" in upgraded["api_key_indexes"]
        assert upgraded["api_key_foreign_keys"] == {
            (("client_id",), "api_client", ("id",))
        }

        _run_alembic(database_url, "downgrade", "20260929_0002")
        downgraded = asyncio.run(_schema(database_url))
        assert downgraded["revision"] == "20260929_0002"
        assert downgraded["document_columns"] == before["document_columns"]
        assert downgraded["document_count"] == 1
        assert "api_client" not in downgraded["tables"]
        assert "api_key" not in downgraded["tables"]
    finally:
        _run_alembic(database_url, "upgrade", "head")


def test_document_owner_migration_preserves_historical_document() -> None:
    database_url = _migration_database_url()
    _run_alembic(database_url, "downgrade", "base")
    try:
        _run_alembic(database_url, "upgrade", "20261002_0003")
        asyncio.run(_insert_document(database_url))
        before = asyncio.run(_schema(database_url))
        assert before["revision"] == "20261002_0003"
        assert before["document_count"] == 1
        assert "client_id" not in before["document_columns"]

        _run_alembic(database_url, "upgrade", "20261003_0004")
        upgraded = asyncio.run(_schema(database_url))
        assert upgraded["revision"] == "20261003_0004"
        assert upgraded["document_count"] == 1
        assert upgraded["document_client_id"] is None
        assert upgraded["document_foreign_keys"] == {
            (("client_id",), "api_client", ("id",))
        }
        assert "ix_document_job_client_id" in upgraded["document_indexes"]

        _run_alembic(database_url, "downgrade", "20261002_0003")
        downgraded = asyncio.run(_schema(database_url))
        assert downgraded["revision"] == "20261002_0003"
        assert downgraded["document_count"] == 1
        assert "client_id" not in downgraded["document_columns"]
    finally:
        _run_alembic(database_url, "upgrade", "head")


async def _insert_document(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO document_job "
                    "(id, document_type, status, avp_number, resume_data) "
                    "VALUES (:id, 'cv', 'pending', 'TEST-MIGRATION', "
                    "CAST('{}' AS jsonb))"
                ).bindparams(bindparam("id", type_=Uuid(as_uuid=True))),
                {"id": DOCUMENT_ID},
            )
    finally:
        await engine.dispose()
