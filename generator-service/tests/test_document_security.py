import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from app.api.dependencies import get_api_key_service
from app.main import app
from app.models.document_job import DocumentJobStatus
from app.services.document_job_service import get_document_job_service
from cv_generator_shared.dto import ApiIdentity

from tests.conftest import FakeDocumentJobService

CLIENT_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CLIENT_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
KEY_A_1 = "cle-a-1"
KEY_A_2 = "cle-a-2"
KEY_B = "cle-b"


class FakeApiKeyService:
    def __init__(self) -> None:
        self.identities = {
            KEY_A_1: ApiIdentity(CLIENT_A, uuid.uuid4(), "Client A"),
            KEY_A_2: ApiIdentity(CLIENT_A, uuid.uuid4(), "Client A"),
            KEY_B: ApiIdentity(CLIENT_B, uuid.uuid4(), "Client B"),
        }
        self.revoked: set[str] = set()
        self.disabled_clients: set[uuid.UUID] = set()

    async def verify_key(self, value: str | None) -> ApiIdentity | None:
        if value is None or value in self.revoked:
            return None
        identity = self.identities.get(value)
        if identity is None or identity.client_id in self.disabled_clients:
            return None
        return identity


@pytest.fixture
async def secured_api() -> AsyncIterator[
    tuple[httpx.AsyncClient, FakeDocumentJobService, FakeApiKeyService]
]:
    documents = FakeDocumentJobService()
    keys = FakeApiKeyService()

    async def override_document_service() -> FakeDocumentJobService:
        return documents

    async def override_key_service() -> FakeApiKeyService:
        return keys

    app.dependency_overrides[get_document_job_service] = override_document_service
    app.dependency_overrides[get_api_key_service] = override_key_service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client, documents, keys
    app.dependency_overrides.clear()


def authentication_header(value: str) -> dict[str, str]:
    return {"X-API-Key": value}


def document_request() -> dict[str, object]:
    return {"avp_number": "1234-26-001", "resume": {"basics": {}}}


@pytest.mark.asyncio
@pytest.mark.parametrize("api_key", [None, "cle-incorrecte"])
async def test_generation_refuses_missing_or_invalid_key_without_creating_job(
    secured_api: tuple[httpx.AsyncClient, FakeDocumentJobService, FakeApiKeyService],
    api_key: str | None,
) -> None:
    client, documents, _ = secured_api
    headers = authentication_header(api_key) if api_key is not None else {}

    response = await client.post(
        "/api/v1/documents/cv", json=document_request(), headers=headers
    )

    assert response.status_code == 401
    assert response.json()["detail"] == {
        "code": "invalid_api_key",
        "message": "Clé API absente ou invalide",
    }
    assert not documents.jobs
    assert api_key is None or api_key not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["cv", "cover-letter"])
async def test_generation_assigns_authenticated_client(
    secured_api: tuple[httpx.AsyncClient, FakeDocumentJobService, FakeApiKeyService],
    path: str,
) -> None:
    client, documents, _ = secured_api

    response = await client.post(
        f"/api/v1/documents/{path}",
        json=document_request(),
        headers=authentication_header(KEY_A_1),
    )

    assert response.status_code == 202
    job = documents.jobs[uuid.UUID(response.json()["id"])]
    assert job.client_id == CLIENT_A


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["/status", "", "/download"])
async def test_only_owner_can_access_every_document_route(
    secured_api: tuple[httpx.AsyncClient, FakeDocumentJobService, FakeApiKeyService],
    suffix: str,
) -> None:
    client, documents, _ = secured_api
    private_content = "= Résultat strictement privé"
    job = documents.add_job(
        DocumentJobStatus.COMPLETED,
        client_id=CLIENT_A,
        result_content=private_content,
        result_format="asciidoc",
    )

    owner_response = await client.get(
        f"/api/v1/documents/{job.id}{suffix}",
        headers=authentication_header(KEY_A_1),
    )
    other_response = await client.get(
        f"/api/v1/documents/{job.id}{suffix}",
        headers=authentication_header(KEY_B),
    )

    assert owner_response.status_code == 200
    assert other_response.status_code == 404
    assert other_response.json()["detail"]["code"] == "document_job_not_found"
    assert "Résultat strictement privé" not in other_response.text


@pytest.mark.asyncio
async def test_unknown_and_historical_documents_are_not_accessible(
    secured_api: tuple[httpx.AsyncClient, FakeDocumentJobService, FakeApiKeyService],
) -> None:
    client, documents, _ = secured_api
    historical = documents.add_job(
        DocumentJobStatus.COMPLETED,
        client_id=None,
        result_content="= Document historique privé",
        result_format="asciidoc",
    )

    unknown_response = await client.get(
        f"/api/v1/documents/{uuid.uuid4()}/status",
        headers=authentication_header(KEY_A_1),
    )
    historical_response = await client.get(
        f"/api/v1/documents/{historical.id}",
        headers=authentication_header(KEY_A_1),
    )

    assert unknown_response.status_code == 404
    assert historical_response.status_code == 404
    assert "Document historique privé" not in historical_response.text


@pytest.mark.asyncio
async def test_revoked_key_is_refused_but_new_key_of_same_client_keeps_access(
    secured_api: tuple[httpx.AsyncClient, FakeDocumentJobService, FakeApiKeyService],
) -> None:
    client, documents, keys = secured_api
    job = documents.add_job(DocumentJobStatus.PENDING, client_id=CLIENT_A)
    keys.revoked.add(KEY_A_1)

    revoked_response = await client.get(
        f"/api/v1/documents/{job.id}/status",
        headers=authentication_header(KEY_A_1),
    )
    renewed_response = await client.get(
        f"/api/v1/documents/{job.id}/status",
        headers=authentication_header(KEY_A_2),
    )

    assert revoked_response.status_code == 401
    assert renewed_response.status_code == 200


@pytest.mark.asyncio
async def test_disabled_client_invalidates_all_keys(
    secured_api: tuple[httpx.AsyncClient, FakeDocumentJobService, FakeApiKeyService],
) -> None:
    client, documents, keys = secured_api
    job = documents.add_job(DocumentJobStatus.PENDING, client_id=CLIENT_A)
    keys.disabled_clients.add(CLIENT_A)

    for api_key in (KEY_A_1, KEY_A_2):
        response = await client.get(
            f"/api/v1/documents/{job.id}/status",
            headers=authentication_header(api_key),
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_remains_public(
    secured_api: tuple[httpx.AsyncClient, FakeDocumentJobService, FakeApiKeyService],
) -> None:
    client, _, _ = secured_api
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


def test_openapi_declares_api_key_security_on_all_document_operations() -> None:
    schema = app.openapi()
    assert schema["components"]["securitySchemes"]["X-API-Key"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
    }
    document_operations = [
        operation
        for path, path_item in schema["paths"].items()
        if path.startswith("/api/v1/documents")
        for method, operation in path_item.items()
        if method in {"get", "post"}
    ]
    assert document_operations
    assert all(
        {"X-API-Key": []} in operation.get("security", [])
        for operation in document_operations
    )
    assert "security" not in schema["paths"]["/api/v1/health"]["get"]
