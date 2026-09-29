import uuid
from io import BytesIO

import httpx
import pytest
from app.models.document_job import DocumentJobStatus, DocumentType
from docx import Document

from tests.conftest import FakeDocumentJobService

ASCIIDOC_CV = """= Camille Exemple

Email : camille@example.nc

== Profil

Professionnelle organisée.

== Compétences

* Rédaction de procédures

== Expériences professionnelles

=== Assistante qualité — Entreprise Exemple

2023 - 2025

== Formation

=== Licence en Gestion — Université Exemple
"""


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
async def test_create_cover_letter_returns_pending_job_without_exposing_resume(
    api_client: httpx.AsyncClient,
    document_service: FakeDocumentJobService,
) -> None:
    resume = {"basics": {"name": "Donnée privée"}, "work": []}

    response = await api_client.post(
        "/api/v1/documents/cover-letter",
        json={"avp_number": " 1234-26-001 ", "resume": resume},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    assert "resume" not in response.json()
    assert "Donnée privée" not in response.text
    job = document_service.jobs[uuid.UUID(response.json()["id"])]
    assert job.document_type is DocumentType.COVER_LETTER
    assert job.avp_number == "1234-26-001"
    assert job.resume_data == resume


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
async def test_completed_cover_letter_uses_existing_result_contract(
    api_client: httpx.AsyncClient,
    document_service: FakeDocumentJobService,
) -> None:
    job = document_service.add_job(
        DocumentJobStatus.COMPLETED,
        document_type=DocumentType.COVER_LETTER,
        result_content="= Lettre de motivation",
        result_format="asciidoc",
    )

    response = await api_client.get(f"/api/v1/documents/{job.id}")

    assert response.status_code == 200
    assert response.json()["type"] == "cover_letter"


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

    assert response.status_code == 409
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"resume": {}},
        {"avp_number": "   ", "resume": {}},
        {"avp_number": "1234-26-001", "resume": []},
    ],
)
async def test_create_cover_letter_rejects_invalid_payload(
    api_client: httpx.AsyncClient,
    payload: dict[str, object],
) -> None:
    response = await api_client.post("/api/v1/documents/cover-letter", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_download_completed_job_returns_readable_docx(
    api_client: httpx.AsyncClient,
    document_service: FakeDocumentJobService,
) -> None:
    job = document_service.add_job(
        DocumentJobStatus.COMPLETED,
        result_content=ASCIIDOC_CV,
        result_format="asciidoc",
    )

    response = await api_client.get(f"/api/v1/documents/{job.id}/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert response.headers["content-disposition"] == (
        f'attachment; filename="cv-{job.id}.docx"'
    )
    document = Document(BytesIO(response.content))
    text = [paragraph.text for paragraph in document.paragraphs]
    assert "Camille Exemple" in text
    assert "Profil" in text
    assert "Rédaction de procédures" in text
    assert "Assistante qualité — Entreprise Exemple" in text
    assert b"must not leak" not in response.content


@pytest.mark.asyncio
async def test_download_cover_letter_uses_type_specific_filename(
    api_client: httpx.AsyncClient,
    document_service: FakeDocumentJobService,
) -> None:
    job = document_service.add_job(
        DocumentJobStatus.COMPLETED,
        document_type=DocumentType.COVER_LETTER,
        result_content="= Lettre de motivation\n\nMadame, Monsieur,\n\nContenu.",
        result_format="asciidoc",
    )

    response = await api_client.get(f"/api/v1/documents/{job.id}/download")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        f'attachment; filename="lettre-motivation-{job.id}.docx"'
    )
    document = Document(BytesIO(response.content))
    assert "Lettre de motivation" in [p.text for p in document.paragraphs]


@pytest.mark.asyncio
async def test_download_unknown_job_returns_not_found(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get(f"/api/v1/documents/{uuid.uuid4()}/download")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "document_job_not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("job_status", "error_code"),
    [
        (DocumentJobStatus.PENDING, "document_not_ready"),
        (DocumentJobStatus.PROCESSING, "document_not_ready"),
        (DocumentJobStatus.FAILED, "document_generation_failed"),
    ],
)
async def test_download_unavailable_job_returns_conflict(
    api_client: httpx.AsyncClient,
    document_service: FakeDocumentJobService,
    job_status: DocumentJobStatus,
    error_code: str,
) -> None:
    job = document_service.add_job(job_status)

    response = await api_client.get(f"/api/v1/documents/{job.id}/download")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == error_code
    assert "must not leak" not in response.text


@pytest.mark.asyncio
async def test_download_completed_job_without_usable_result_is_controlled(
    api_client: httpx.AsyncClient,
    document_service: FakeDocumentJobService,
) -> None:
    job = document_service.add_job(
        DocumentJobStatus.COMPLETED,
        result_content="   ",
        result_format="asciidoc",
    )

    response = await api_client.get(f"/api/v1/documents/{job.id}/download")

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "document_result_unavailable",
        "message": "Document result is unavailable",
    }
    assert "must not leak" not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result_content", "result_format"),
    [
        (None, "asciidoc"),
        (ASCIIDOC_CV, "markdown"),
    ],
)
async def test_download_completed_job_with_unavailable_result_returns_conflict(
    api_client: httpx.AsyncClient,
    document_service: FakeDocumentJobService,
    result_content: str | None,
    result_format: str,
) -> None:
    job = document_service.add_job(
        DocumentJobStatus.COMPLETED,
        result_content=result_content,
        result_format=result_format,
    )

    response = await api_client.get(f"/api/v1/documents/{job.id}/download")

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "document_result_unavailable",
        "message": "Document result is unavailable",
    }
