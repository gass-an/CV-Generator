import asyncio
import struct
from pathlib import Path

import httpx
import pytest
from app.config import get_settings
from app.database import async_session_factory
from app.llm_router import LlmRouterError, RouterModel
from app.main import app
from cv_generator_shared.document_jobs import (
    DocumentJob,
    DocumentJobStatus,
    DocumentType,
)
from cv_generator_shared.llm_models import LlmConfiguration
from sqlalchemy import select

from conftest import login

MODEL_A = "ggml-org/Qwen3-14B-GGUF:Q4_K_M"
MODEL_B = "org/second-model-GGUF:Q4_K_M"
MODEL_C = "org/third-model-GGUF:Q5_K_M"


def _write_cached_model(cache_root: Path) -> Path:
    repository = cache_root / "models--ggml-org--Qwen3-14B-GGUF"
    blob = repository / "blobs" / "model-blob"
    snapshot = repository / "snapshots" / "revision"
    blob.parent.mkdir(parents=True)
    snapshot.mkdir(parents=True)
    values = {
        "general.architecture": (8, "qwen3"),
        "qwen3.block_count": (4, 40),
        "qwen3.embedding_length": (4, 5120),
        "qwen3.attention.head_count": (4, 40),
        "qwen3.attention.head_count_kv": (4, 8),
    }
    content = bytearray(b"GGUF" + struct.pack("<IQQ", 3, 0, len(values)))
    for key, (value_type, value) in values.items():
        encoded_key = key.encode()
        content.extend(struct.pack("<Q", len(encoded_key)) + encoded_key)
        content.extend(struct.pack("<I", value_type))
        if value_type == 8:
            encoded_value = value.encode()
            content.extend(struct.pack("<Q", len(encoded_value)) + encoded_value)
        else:
            content.extend(struct.pack("<I", value))
    blob.write_bytes(content + bytes(1024))
    (snapshot / "Qwen3-14B-Q4_K_M.gguf").symlink_to(Path("../../blobs/model-blob"))
    return blob


class FakeRouter:
    def __init__(self) -> None:
        self.loaded = MODEL_A
        self.downloaded: list[str] = []
        self.failed_loads: set[str] = set()
        self.failed_loads_still_running: set[str] = set()
        self.failed_unloads: set[str] = set()
        self.status_sequences: dict[str, list[str]] = {}
        self.load_delay = 0.0
        self.loads_in_flight = 0
        self.max_loads_in_flight = 0
        self.unavailable = False
        self.events: list[tuple[str, str]] = []

    async def list_models(self) -> list[RouterModel]:
        if self.unavailable:
            raise LlmRouterError("Le serveur LLM est indisponible")
        return [
            RouterModel(
                id=model,
                status=(
                    self.status_sequences[model].pop(0)
                    if self.status_sequences.get(model)
                    else "loaded"
                    if model == self.loaded
                    else "unloaded"
                ),
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
        self.events.append(("load", model))
        self.loads_in_flight += 1
        self.max_loads_in_flight = max(self.max_loads_in_flight, self.loads_in_flight)
        try:
            if self.load_delay:
                await asyncio.sleep(self.load_delay)
            self.loaded = model
        finally:
            self.loads_in_flight -= 1

    async def wait_until_loaded(self, model: str) -> None:
        self.events.append(("wait_loaded", model))
        if model in self.failed_loads:
            if model not in self.failed_loads_still_running:
                self.loaded = ""
            raise LlmRouterError(f"Échec simulé pour {model}")

    async def unload(self, model: str) -> None:
        self.events.append(("unload", model))
        if model in self.failed_unloads:
            raise LlmRouterError(f"Déchargement simulé en échec pour {model}")
        if self.loaded == model:
            self.loaded = ""

    async def wait_until_unloaded(self, model: str) -> None:
        self.events.append(("wait_unloaded", model))
        if model in self.failed_unloads:
            raise LlmRouterError(f"Déchargement simulé en échec pour {model}")


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
    assert response.json()["models"][0]["size"] == 1024
    assert response.json()["models"][0]["vram_estimate"] is None


@pytest.mark.asyncio
async def test_data_discovers_cached_model_when_router_has_no_path(
    browser: httpx.AsyncClient,
    managed_router: FakeRouter,
    tmp_path: Path,
) -> None:
    del managed_router
    blob = _write_cached_model(tmp_path)
    settings = get_settings()
    previous_cache_path = settings.llm_cache_path
    settings.llm_cache_path = str(tmp_path)
    try:
        await login(browser)
        response = await browser.get("/llm-models/data")
    finally:
        settings.llm_cache_path = previous_cache_path

    assert response.status_code == 200
    selected = next(model for model in response.json()["models"] if model["selected"])
    assert selected["size"] == blob.stat().st_size
    assert selected["size_label"] != "Taille inconnue"
    assert selected["vram_estimate"] is not None
    assert selected["vram_estimate_label"] != "Estimation indisponible"


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
async def test_models_page_renders_primary_card_and_collapsible_download(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    await login(browser)
    page = await browser.get("/llm-models")
    assert page.status_code == 200
    assert 'class="model-card model-card-primary"' in page.text
    assert "Décharger de la VRAM" in page.text
    assert "+ Ajouter un modèle depuis Hugging Face" in page.text
    assert "Modèles connus" not in page.text


@pytest.mark.asyncio
async def test_sleeping_model_keeps_exact_status_and_sleep_actions(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    managed_router.status_sequences[MODEL_A] = ["sleeping", "sleeping"]
    await login(browser)

    data = await browser.get("/llm-models/data")
    page = await browser.get("/llm-models")

    selected = next(model for model in data.json()["models"] if model["selected"])
    assert selected["status"] == "sleeping"
    assert selected["status_label"] == "En veille"
    assert selected["loaded"] is False
    assert data.json()["loaded_model"] == MODEL_A
    assert "En veille" in page.text
    assert "Décharger complètement" in page.text
    assert "Prêt pour la génération" not in page.text
    assert managed_router.events == []


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
    assert managed_router.events == [
        ("unload", MODEL_A),
        ("wait_unloaded", MODEL_A),
        ("load", MODEL_B),
        ("wait_loaded", MODEL_B),
    ]
    async with async_session_factory() as session:
        selected = await session.scalar(select(LlmConfiguration.selected_model))
    assert selected == MODEL_B


@pytest.mark.asyncio
async def test_activation_unloads_sleeping_previous_model_before_switch(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    managed_router.status_sequences[MODEL_A] = ["sleeping"]
    csrf = await login(browser)

    response = await browser.post(
        "/llm-models/activate",
        data={"csrf_token": csrf, "model": MODEL_B},
    )

    assert response.status_code == 303
    assert managed_router.events == [
        ("unload", MODEL_A),
        ("wait_unloaded", MODEL_A),
        ("load", MODEL_B),
        ("wait_loaded", MODEL_B),
    ]
    async with async_session_factory() as session:
        assert await session.scalar(select(LlmConfiguration.selected_model)) == MODEL_B


@pytest.mark.asyncio
async def test_failed_activation_restores_previous_model_and_selection(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    managed_router.failed_loads.add(MODEL_B)
    managed_router.failed_loads_still_running.add(MODEL_B)
    csrf = await login(browser)
    response = await browser.post(
        "/llm-models/activate",
        data={"csrf_token": csrf, "model": MODEL_B},
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "error=" in location
    assert "ancien%20mod%C3%A8le%20a%20%C3%A9t%C3%A9%20restaur%C3%A9" in location
    assert managed_router.loaded == MODEL_A
    assert managed_router.events == [
        ("unload", MODEL_A),
        ("wait_unloaded", MODEL_A),
        ("load", MODEL_B),
        ("wait_loaded", MODEL_B),
        ("unload", MODEL_B),
        ("wait_unloaded", MODEL_B),
        ("load", MODEL_A),
        ("wait_loaded", MODEL_A),
    ]
    async with async_session_factory() as session:
        selected = await session.scalar(select(LlmConfiguration.selected_model))
    assert selected == MODEL_A


@pytest.mark.asyncio
async def test_failed_unload_keeps_loaded_previous_without_retrying_it(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    managed_router.failed_unloads.add(MODEL_A)
    managed_router.failed_loads.add(MODEL_B)
    csrf = await login(browser)
    response = await browser.post(
        "/llm-models/activate",
        data={"csrf_token": csrf, "model": MODEL_B},
    )
    assert response.status_code == 303
    assert managed_router.events == [("unload", MODEL_A)]
    assert managed_router.loaded == MODEL_A
    async with async_session_factory() as session:
        assert await session.scalar(select(LlmConfiguration.selected_model)) == MODEL_A


@pytest.mark.asyncio
async def test_rollback_waits_for_previous_loading_without_reloading(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    managed_router.failed_loads.add(MODEL_B)
    managed_router.failed_loads_still_running.add(MODEL_B)
    managed_router.status_sequences[MODEL_A] = [
        "loaded",
        "unloaded",
        "loading",
        "loading",
        "loaded",
    ]
    csrf = await login(browser)
    response = await browser.post(
        "/llm-models/activate",
        data={"csrf_token": csrf, "model": MODEL_B},
    )
    assert response.status_code == 303
    assert managed_router.events == [
        ("unload", MODEL_A),
        ("wait_unloaded", MODEL_A),
        ("load", MODEL_B),
        ("wait_loaded", MODEL_B),
        ("unload", MODEL_B),
        ("wait_unloaded", MODEL_B),
        ("wait_loaded", MODEL_A),
    ]


@pytest.mark.asyncio
async def test_sleeping_previous_model_is_kept_active_without_reload(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    managed_router.status_sequences[MODEL_A] = [
        "sleeping",
        "unloaded",
        "sleeping",
        "sleeping",
    ]
    managed_router.failed_loads.add(MODEL_B)
    managed_router.failed_loads_still_running.add(MODEL_B)
    csrf = await login(browser)
    response = await browser.post(
        "/llm-models/activate",
        data={"csrf_token": csrf, "model": MODEL_B},
    )
    assert response.status_code == 303
    assert managed_router.events == [
        ("unload", MODEL_A),
        ("wait_unloaded", MODEL_A),
        ("load", MODEL_B),
        ("wait_loaded", MODEL_B),
        ("unload", MODEL_B),
        ("wait_unloaded", MODEL_B),
    ]


@pytest.mark.asyncio
async def test_activation_waits_for_target_already_loading(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    managed_router.status_sequences[MODEL_B] = ["loading"]
    csrf = await login(browser)
    response = await browser.post(
        "/llm-models/activate",
        data={"csrf_token": csrf, "model": MODEL_B},
    )
    assert response.status_code == 303
    assert managed_router.events == [
        ("unload", MODEL_A),
        ("wait_unloaded", MODEL_A),
        ("wait_loaded", MODEL_B),
    ]


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
    assert "aucun%20mod%C3%A8le" in response.headers["location"]
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


@pytest.mark.asyncio
async def test_pending_job_still_blocks_model_switch(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    async with async_session_factory() as session, session.begin():
        session.add(
            DocumentJob(
                document_type=DocumentType.CV,
                status=DocumentJobStatus.PENDING,
                avp_number="TEST-ADMIN-LLM-LOCK",
                resume_data={"basics": {}},
                llm_model=MODEL_A,
            )
        )
    csrf = await login(browser)
    response = await browser.post(
        "/llm-models/activate",
        data={"csrf_token": csrf, "model": MODEL_B},
    )
    assert response.status_code == 303
    assert "error=" in response.headers["location"]
    assert managed_router.events == []
    async with async_session_factory() as session:
        selected = await session.scalar(select(LlmConfiguration.selected_model))
    assert selected == MODEL_A


@pytest.mark.asyncio
async def test_selected_model_can_be_unloaded_without_changing_selection(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    csrf = await login(browser)
    response = await browser.post(
        "/llm-models/unload",
        data={"csrf_token": csrf, "model": MODEL_A},
    )
    assert response.status_code == 303
    assert managed_router.loaded == ""
    assert managed_router.events == [
        ("unload", MODEL_A),
        ("wait_unloaded", MODEL_A),
    ]
    async with async_session_factory() as session:
        assert await session.scalar(select(LlmConfiguration.selected_model)) == MODEL_A


@pytest.mark.asyncio
async def test_sleeping_selected_model_can_be_fully_unloaded(
    browser: httpx.AsyncClient, managed_router: FakeRouter
) -> None:
    managed_router.status_sequences[MODEL_A] = ["sleeping"]
    csrf = await login(browser)

    response = await browser.post(
        "/llm-models/unload",
        data={"csrf_token": csrf, "model": MODEL_A},
    )

    assert response.status_code == 303
    assert managed_router.events == [
        ("unload", MODEL_A),
        ("wait_unloaded", MODEL_A),
    ]
    async with async_session_factory() as session:
        assert await session.scalar(select(LlmConfiguration.selected_model)) == MODEL_A


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "job_status", [DocumentJobStatus.PENDING, DocumentJobStatus.PROCESSING]
)
async def test_active_job_blocks_manual_unload(
    browser: httpx.AsyncClient,
    managed_router: FakeRouter,
    job_status: DocumentJobStatus,
) -> None:
    async with async_session_factory() as session, session.begin():
        session.add(
            DocumentJob(
                document_type=DocumentType.CV,
                status=job_status,
                avp_number="TEST-ADMIN-LLM-UNLOAD-LOCK",
                resume_data={"basics": {}},
                llm_model=MODEL_A,
            )
        )
    csrf = await login(browser)
    response = await browser.post(
        "/llm-models/unload",
        data={"csrf_token": csrf, "model": MODEL_A},
    )
    assert response.status_code == 303
    assert "error=" in response.headers["location"]
    assert managed_router.events == []
