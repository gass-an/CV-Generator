import uuid

import httpx
import pytest
from app.models.document_job import DocumentJobStatus

from tests.conftest import FakeDocumentJobService


@pytest.mark.asyncio
async def test_create_cv_document_returns_pending_job(
    api_client: httpx.AsyncClient,
    document_service: FakeDocumentJobService,
) -> None:
    response = await api_client.post(
        "/api/v1/documents/cv",
        json={
            "avp_number": "1234-26-001",
            "resume": {
                "basics": {},
                "work": [],
                "education": [],
                "skills": [],
            },
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "pending"
    created_job = document_service.jobs[uuid.UUID(payload["id"])]
    assert created_job.status is DocumentJobStatus.PENDING
    assert created_job.avp_number == "1234-26-001"


@pytest.mark.asyncio
async def test_get_status_does_not_expose_resume(
    api_client: httpx.AsyncClient,
    document_service: FakeDocumentJobService,
) -> None:
    job = document_service.add_job(DocumentJobStatus.PENDING)

    response = await api_client.get(f"/api/v1/documents/{job.id}/status")

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert "resume" not in response.json()
    assert "resume_data" not in response.json()


@pytest.mark.asyncio
async def test_unknown_job_returns_not_found(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(f"/api/v1/documents/{uuid.uuid4()}/status")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "document_job_not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "job_status",
    [DocumentJobStatus.PENDING, DocumentJobStatus.PROCESSING],
)
async def test_unfinished_job_result_returns_conflict(
    api_client: httpx.AsyncClient,
    document_service: FakeDocumentJobService,
    job_status: DocumentJobStatus,
) -> None:
    job = document_service.add_job(job_status)

    response = await api_client.get(f"/api/v1/documents/{job.id}")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "document_not_ready"


@pytest.mark.asyncio
async def test_completed_job_returns_asciidoc(
    api_client: httpx.AsyncClient,
    document_service: FakeDocumentJobService,
) -> None:
    job = document_service.add_job(
        DocumentJobStatus.COMPLETED,
        result_content="= Exemple",
        result_format="asciidoc",
    )

    response = await api_client.get(f"/api/v1/documents/{job.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(job.id),
        "type": "cv",
        "format": "asciidoc",
        "content": "= Exemple",
    }


@pytest.mark.asyncio
async def test_failed_job_returns_safe_business_error(
    api_client: httpx.AsyncClient,
    document_service: FakeDocumentJobService,
) -> None:
    private_error = "postgresql://user:secret@postgres/internal SQL failure"
    job = document_service.add_job(
        DocumentJobStatus.FAILED,
        error_message=private_error,
    )

    response = await api_client.get(f"/api/v1/documents/{job.id}")

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "document_generation_failed",
        "message": "Document generation failed",
    }
    assert private_error not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"resume": {}},
        {"avp_number": "", "resume": {}},
        {"avp_number": "   ", "resume": {}},
        {"avp_number": "1" * 129, "resume": {}},
        {"avp_number": "1234-26-001", "resume": []},
    ],
)
async def test_create_cv_document_rejects_invalid_payload(
    api_client: httpx.AsyncClient,
    payload: dict[str, object],
) -> None:
    response = await api_client.post("/api/v1/documents/cv", json=payload)

    assert response.status_code == 422
