import json

import httpx
import pytest
from app.llm_router import (
    LlmRouterClient,
    LlmRouterError,
    LlmRouterInvalidResponseError,
    LlmRouterLoadTimeoutError,
    LlmRouterUnavailableError,
    LlmRouterUnloadTimeoutError,
)


def client_for(handler: httpx.MockTransport) -> LlmRouterClient:
    return LlmRouterClient(
        base_url="http://router.internal:8080",
        timeout=5,
        activation_timeout=30,
        http_client=httpx.AsyncClient(transport=handler),
    )


@pytest.mark.asyncio
async def test_lists_models_and_real_download_progress() -> None:
    client = client_for(
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "org/model-GGUF:Q4_K_M",
                            "status": {
                                "value": "downloading",
                                "progress": {
                                    "https://huggingface.co/model.gguf": {
                                        "done": 25,
                                        "total": 100,
                                    }
                                },
                            },
                        }
                    ]
                },
            )
        )
    )
    models = await client.list_models()
    assert models[0].progress_done == 25
    assert models[0].progress_total == 100
    assert models[0].quantization == "Q4_K_M"
    await client.aclose()


@pytest.mark.asyncio
async def test_download_posts_only_model_reference() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/models"
        assert json.loads(request.content) == {"model": "org/model-GGUF:Q4_K_M"}
        return httpx.Response(200, json={"success": True})

    client = client_for(httpx.MockTransport(handler))
    await client.download("org/model-GGUF:Q4_K_M")
    await client.aclose()


@pytest.mark.asyncio
async def test_rejects_unconfirmed_operation() -> None:
    client = client_for(
        httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    )
    with pytest.raises(LlmRouterInvalidResponseError):
        await client.load("org/model-GGUF:Q4_K_M")
    await client.aclose()


@pytest.mark.asyncio
async def test_maps_timeout_to_safe_unavailability_message() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    unavailable = client_for(httpx.MockTransport(timeout))
    with pytest.raises(LlmRouterUnavailableError, match="délai autorisé"):
        await unavailable.list_models()
    await unavailable.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "transport_error",
    [
        httpx.ConnectError("connection failed"),
        httpx.RemoteProtocolError("peer closed connection"),
    ],
)
async def test_maps_all_httpx_request_errors_to_router_unavailability(
    transport_error: httpx.RequestError,
) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        transport_error.request = request
        raise transport_error

    client = client_for(httpx.MockTransport(fail))
    with pytest.raises(
        LlmRouterUnavailableError, match="serveur LLM est indisponible"
    ) as captured:
        await client.list_models()
    assert "connection failed" not in str(captured.value)
    assert "peer closed connection" not in str(captured.value)
    await client.aclose()


@pytest.mark.asyncio
async def test_maps_invalid_json_to_invalid_response_without_internal_details() -> None:
    invalid = client_for(
        httpx.MockTransport(lambda request: httpx.Response(200, text="invalid"))
    )
    with pytest.raises(
        LlmRouterInvalidResponseError, match="Réponse invalide du serveur LLM"
    ) as captured:
        await invalid.list_models()
    assert "JSON" not in str(captured.value)
    await invalid.aclose()


@pytest.mark.asyncio
async def test_maps_http_error_to_safe_router_error() -> None:
    client = client_for(
        httpx.MockTransport(
            lambda request: httpx.Response(
                502, text="private upstream detail", request=request
            )
        )
    )
    with pytest.raises(LlmRouterError, match="opération a été refusée") as captured:
        await client.list_models()
    assert "private upstream detail" not in str(captured.value)
    await client.aclose()


@pytest.mark.asyncio
async def test_waits_for_loading_to_become_loaded() -> None:
    statuses = iter(["unloaded", "loading", "loaded"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "org/model-GGUF:Q4_K_M",
                        "status": {"value": next(statuses)},
                    }
                ]
            },
        )

    client = client_for(httpx.MockTransport(handler))
    await client.wait_until_loaded("org/model-GGUF:Q4_K_M", poll_interval=0)
    await client.aclose()


@pytest.mark.asyncio
async def test_loading_failure_is_not_confirmed() -> None:
    client = client_for(
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "org/model-GGUF:Q4_K_M",
                            "status": {"value": "unloaded", "failed": True},
                        }
                    ]
                },
            )
        )
    )
    with pytest.raises(LlmRouterError, match="a échoué"):
        await client.wait_until_loaded("org/model-GGUF:Q4_K_M", poll_interval=0)
    await client.aclose()


@pytest.mark.asyncio
async def test_loading_timeout_is_bounded() -> None:
    client = LlmRouterClient(
        base_url="http://router.internal:8080",
        timeout=5,
        activation_timeout=0.001,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "data": [
                            {
                                "id": "org/model-GGUF:Q4_K_M",
                                "status": {"value": "loading"},
                            }
                        ]
                    },
                )
            )
        ),
    )
    with pytest.raises(LlmRouterLoadTimeoutError):
        await client.wait_until_loaded("org/model-GGUF:Q4_K_M", poll_interval=0)
    await client.aclose()


@pytest.mark.asyncio
async def test_waits_for_loaded_model_to_become_unloaded() -> None:
    statuses = iter(["loaded", "loaded", "unloaded"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "org/model-GGUF:Q4_K_M",
                        "status": {"value": next(statuses)},
                    }
                ]
            },
        )

    client = client_for(httpx.MockTransport(handler))
    await client.wait_until_unloaded("org/model-GGUF:Q4_K_M", poll_interval=0)
    await client.aclose()


@pytest.mark.asyncio
async def test_unloading_timeout_is_bounded() -> None:
    client = LlmRouterClient(
        base_url="http://router.internal:8080",
        timeout=5,
        activation_timeout=0.001,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "data": [
                            {
                                "id": "org/model-GGUF:Q4_K_M",
                                "status": {"value": "loaded"},
                            }
                        ]
                    },
                )
            )
        ),
    )
    with pytest.raises(LlmRouterUnloadTimeoutError):
        await client.wait_until_unloaded("org/model-GGUF:Q4_K_M", poll_interval=0)
    await client.aclose()
