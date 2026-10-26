import asyncio

import httpx
import pytest
from app.config import get_settings
from app.database import async_session_factory
from app.llm_router import LlmRouterError, RouterModel
from app.main import app
from cv_generator_shared.llm_models import LlmConfiguration
from sqlalchemy import select

from conftest import login

MODEL_A = "ggml-org/Qwen3-14B-GGUF:Q4_K_M"
MODEL_B = "org/second-model-GGUF:Q4_K_M"
MODEL_C = "org/third-model-GGUF:Q5_K_M"


class FakeRouter:
    def __init__(self) -> None:
        self.loaded = MODEL_A
        self.downloaded: list[str] = []
        self.failed_loads: set[str] = set()
        self.load_delay = 0.0
        self.loads_in_flight = 0
        self.max_loads_in_flight = 0
        self.unavailable = False

    async def list_models(self) -> list[RouterModel]:
        if self.unavailable:
            raise LlmRouterError("Le serveur LLM est indisponible")
        return [
            RouterModel(
                id=model,
                status="loaded" if model == self.loaded else "unloaded",
                size=1024,
                progress_done=None,
                progress_total=None,
                failed=False,
            )
            for model in (MODEL_A, MODEL_B, MODEL_C)
        ]

    async def download(self, model: str) -> None:
        self.downloaded.append(model)

    async def load(self, model: str) -> None:
        self.loads_in_flight += 1
        self.max_loads_in_flight = max(self.max_loads_in_flight, self.loads_in_flight)
        try:
            if self.load_delay:
                await asyncio.sleep(self.load_delay)
            self.loaded = model
        finally:
            self.loads_in_flight -= 1

    async def wait_until_loaded(self, model: str) -> None:
        if model in self.failed_loads:
            self.loaded = ""
            raise LlmRouterError(f"Échec simulé pour {model}")

    async def unload(self, model: str) -> None:
        if self.loaded == model:
            self.loaded = ""


@pytest.fixture
async def managed_router() -> FakeRouter:
    settings = get_settings()
    old_enabled = settings.llm_management_enabled
    old_base_url = settings.llm_base_url
    old_router = getattr(app.state, "llm_router", None)
    router = FakeRouter()
    settings.llm_management_enabled = True
    settings.llm_base_url = "http://router.internal:8080"
    app.state.llm_router = router
    async with async_session_factory() as session, session.begin():
        configuration = await session.get(LlmConfiguration, 1)
        assert configuration is not None
        configuration.selected_model = MODEL_A
    yield router
    settings.llm_management_enabled = old_enabled
    settings.llm_base_url = old_base_url
    if old_router is None:
        del app.state.llm_router
    else:
        app.state.llm_router = old_router


@pytest.mark.asyncio
async def test_models_page_and_data_are_private(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    assert (await browser.get("/llm-models/data")).status_code == 401
    await login(browser)
    response = await browser.get("/llm-models/data")
    assert response.status_code == 200
    assert response.json()["loaded_model"] == MODEL_A


@pytest.mark.asyncio
async def test_unavailable_page_keeps_automatic_recovery_root(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    managed_router.unavailable = True
    await login(browser)
    page = await browser.get("/llm-models")
    assert page.status_code == 200
    assert "Serveur LLM indisponible" in page.text
    assert "data-models-root" in page.text
    managed_router.unavailable = False
    data = await browser.get("/llm-models/data")
    assert data.status_code == 200
    assert data.json()["loaded_model"] == MODEL_A


@pytest.mark.asyncio
async def test_models_page_keeps_table_cells_around_flexible_content(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    await login(browser)
    page = await browser.get("/llm-models")
    assert page.status_code == 200
    assert '<div class="model-roles">' in page.text
    assert '<div class="model-actions">' in page.text
    assert '<td class="model-actions">' not in page.text


@pytest.mark.asyncio
async def test_invalid_reference_and_csrf_are_rejected(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    csrf = await login(browser)
    invalid_csrf = await browser.post(
        "/llm-models/download",
        data={"csrf_token": "invalid", "model": MODEL_B},
    )
    assert invalid_csrf.status_code == 403
    invalid_model = await browser.post(
        "/llm-models/download",
        data={"csrf_token": csrf, "model": "https://attacker/model.gguf"},
    )
    assert invalid_model.status_code == 303
    assert "error=" in invalid_model.headers["location"]
    assert managed_router.downloaded == []


@pytest.mark.asyncio
async def test_activation_is_confirmed_before_persistence(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    csrf = await login(browser)
    response = await browser.post(
        "/llm-models/activate",
        data={"csrf_token": csrf, "model": MODEL_B},
    )
    assert response.status_code == 303
    assert "message=" in response.headers["location"]
    assert managed_router.loaded == MODEL_B
    async with async_session_factory() as session:
        selected = await session.scalar(select(LlmConfiguration.selected_model))
    assert selected == MODEL_B


@pytest.mark.asyncio
async def test_failed_activation_restores_previous_model_and_selection(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    managed_router.failed_loads.add(MODEL_B)
    csrf = await login(browser)
    response = await browser.post(
        "/llm-models/activate",
        data={"csrf_token": csrf, "model": MODEL_B},
    )
    assert response.status_code == 303
    assert "error=" in response.headers["location"]
    assert managed_router.loaded == MODEL_A
    async with async_session_factory() as session:
        selected = await session.scalar(select(LlmConfiguration.selected_model))
    assert selected == MODEL_A


@pytest.mark.asyncio
async def test_failed_rollback_is_reported_without_persisting_target(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    managed_router.failed_loads.update({MODEL_A, MODEL_B})
    csrf = await login(browser)
    response = await browser.post(
        "/llm-models/activate",
        data={"csrf_token": csrf, "model": MODEL_B},
    )
    assert response.status_code == 303
    assert "ancien%20mod%C3%A8le" in response.headers["location"]
    async with async_session_factory() as session:
        selected = await session.scalar(select(LlmConfiguration.selected_model))
    assert selected == MODEL_A


@pytest.mark.asyncio
async def test_concurrent_activations_are_serialized(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    managed_router.load_delay = 0.02
    csrf = await login(browser)
    responses = await asyncio.gather(
        browser.post(
            "/llm-models/activate",
            data={"csrf_token": csrf, "model": MODEL_B},
        ),
        browser.post(
            "/llm-models/activate",
            data={"csrf_token": csrf, "model": MODEL_C},
        ),
    )
    assert all(response.status_code == 303 for response in responses)
    assert managed_router.max_loads_in_flight == 1
