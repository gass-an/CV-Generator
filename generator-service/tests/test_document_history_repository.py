import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from app.models.document_job import DocumentJobStatus, DocumentType
from app.repositories.document_job_repository import DocumentJobRepository
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_history_uses_filtered_projection_stable_order_and_separate_total() -> (
    None
):
    session = AsyncMock(spec=AsyncSession)
    page_result = Mock()
    page_result.all.return_value = [
        SimpleNamespace(
            id=uuid.uuid4(),
            document_type=DocumentType.CV,
            status=DocumentJobStatus.COMPLETED,
            avp_number="3134-26-1382/SR",
            candidate_name="Camille Exemple",
            created_at=datetime.now(UTC),
            started_at=None,
            completed_at=None,
        )
    ]
    count_result = Mock()
    count_result.scalar_one.return_value = 3
    session.execute.side_effect = [page_result, count_result]
    client_id = uuid.uuid4()

    items, total = await DocumentJobRepository(session).list_for_client(
        client_id=client_id,
        limit=10,
        offset=2,
        document_type=DocumentType.CV,
        status=DocumentJobStatus.COMPLETED,
        avp_number="3134-26-1382/SR",
    )

    page_statement = session.execute.await_args_list[0].args[0]
    count_statement = session.execute.await_args_list[1].args[0]
    page_sql = str(page_statement.compile(dialect=postgresql.dialect()))
    count_sql = str(count_statement.compile(dialect=postgresql.dialect()))
    assert "result_content" not in page_sql
    assert "resume_data AS resume_data" not in page_sql
    assert "jsonb_typeof" in page_sql
    assert "document_job.client_id" in page_sql
    assert "document_job.document_type" in page_sql
    assert "document_job.status" in page_sql
    assert "btrim(document_job.avp_number)" in page_sql
    assert "ORDER BY document_job.created_at DESC, document_job.id DESC" in page_sql
    assert "LIMIT" in page_sql and "OFFSET" in page_sql
    assert "count(document_job.id)" in count_sql
    assert total == 3
    assert items[0].candidate_name == "Camille Exemple"


@pytest.mark.asyncio
async def test_history_exact_avp_filter_trims_stored_peripheral_spaces() -> None:
    session = AsyncMock(spec=AsyncSession)
    page_result = Mock()
    page_result.all.return_value = []
    count_result = Mock()
    count_result.scalar_one.return_value = 0
    session.execute.side_effect = [page_result, count_result]

    await DocumentJobRepository(session).list_for_client(
        client_id=uuid.uuid4(),
        limit=20,
        offset=0,
        avp_number="3134-26-1382/SR",
    )

    for call in session.execute.await_args_list:
        statement = call.args[0]
        sql = str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        assert "btrim(document_job.avp_number) = '3134-26-1382/SR'" in sql


@pytest.mark.asyncio
async def test_distinct_avp_query_is_sorted_prefixed_and_scoped_to_client() -> None:
    session = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalars.return_value.all.return_value = ["a", "az"]
    session.execute.return_value = result

    values = await DocumentJobRepository(session).list_distinct_avp_numbers_for_client(
        client_id=uuid.uuid4(),
        prefix="a",
    )

    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "document_job.client_id" in sql
    assert "lower(btrim(document_job.avp_number))" in sql
    assert "ILIKE" in sql
    assert "GROUP BY btrim(document_job.avp_number)" in sql
    assert values == ["a", "az"]
