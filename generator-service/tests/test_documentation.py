import httpx
import pytest
from app.main import app


@pytest.mark.asyncio
async def test_docs_uses_redoc_and_keeps_openapi_schema(
    api_client: httpx.AsyncClient,
) -> None:
    docs_response = await api_client.get("/docs")

    assert docs_response.status_code == 200
    assert "text/html" in docs_response.headers["content-type"]
    assert "redoc.standalone.js" in docs_response.text
    assert "swagger-ui" not in docs_response.text.lower()
    assert 'spec-url="/openapi.json"' in docs_response.text

    assert (await api_client.get("/redoc")).status_code == 404

    schema_response = await api_client.get("/openapi.json")
    assert schema_response.status_code == 200
    schema = schema_response.json()
    assert schema["info"]["version"] == app.version == "test"
    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/documents/cv" in schema["paths"]
