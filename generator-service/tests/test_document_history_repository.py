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
    assert "ORDER BY document_job.created_at DESC, document_job.id DESC" in page_sql
    assert "LIMIT" in page_sql and "OFFSET" in page_sql
    assert "count(document_job.id)" in count_sql
    assert total == 3
    assert items[0].candidate_name == "Camille Exemple"
