import json

import httpx
import pytest
from app.clients.llm_client import (
    LlmClient,
    LlmClientError,
    LlmInvalidResponseError,
    LlmTimeoutError,
)

BASE_URL = "http://llama.example"
MESSAGES = [
    {"role": "system", "content": "Règles"},
    {"role": "user", "content": "Données"},
]


def make_client(handler: httpx.MockTransport) -> LlmClient:
    return LlmClient(
        base_url=BASE_URL,
        model="local-model",
        timeout=120,
        http_client=httpx.AsyncClient(transport=handler),
    )


@pytest.mark.asyncio
async def test_generate_sends_openai_compatible_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"{BASE_URL}/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload == {
            "model": "local-model",
            "messages": MESSAGES,
            "stream": False,
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "  = Jeanne Exemple  "}}]},
        )

    client = make_client(httpx.MockTransport(handler))
    assert await client.generate(MESSAGES) == "= Jeanne Exemple"
    await client.aclose()


@pytest.mark.asyncio
async def test_generate_maps_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    client = make_client(httpx.MockTransport(handler))
    with pytest.raises(LlmTimeoutError):
        await client.generate(MESSAGES)
    await client.aclose()


@pytest.mark.asyncio
async def test_generate_maps_http_error() -> None:
    client = make_client(
        httpx.MockTransport(lambda request: httpx.Response(500, text="private"))
    )
    with pytest.raises(LlmClientError, match="requête vers l'API du LLM a échoué"):
        await client.generate(MESSAGES)
    await client.aclose()


@pytest.mark.asyncio
async def test_generate_rejects_invalid_json() -> None:
    client = make_client(
        httpx.MockTransport(lambda request: httpx.Response(200, text="not-json"))
    )
    with pytest.raises(LlmInvalidResponseError, match="JSON valide"):
        await client.generate(MESSAGES)
    await client.aclose()


@pytest.mark.asyncio
async def test_generate_rejects_truncated_response() -> None:
    client = make_client(
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "length",
                            "message": {"content": "= CV incomplet"},
                        }
                    ]
                },
            )
        )
    )
    with pytest.raises(LlmInvalidResponseError, match="tronquée"):
        await client.generate(MESSAGES)
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "aucun choix"),
        ({"choices": []}, "aucun choix"),
        ({"choices": [{}]}, "aucun message"),
        ({"choices": [{"message": {}}]}, "contenu.*vide"),
        ({"choices": [{"message": {"content": "  "}}]}, "contenu.*vide"),
        ({"choices": [{"message": {"content": 42}}]}, "contenu.*vide"),
    ],
)
async def test_generate_rejects_invalid_response_structure(
    payload: object,
    message: str,
) -> None:
    client = make_client(
        httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    )
    with pytest.raises(LlmInvalidResponseError, match=message):
        await client.generate(MESSAGES)
    await client.aclose()
