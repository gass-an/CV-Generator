from dataclasses import dataclass

from cv_generator_shared.document_jobs import DocumentJob, DocumentJobStatus
from cv_generator_shared.llm import (
    get_llm_configuration_for_update,
    lock_llm_configuration,
    normalize_hf_model_reference,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm_router import LlmRouterClient, LlmRouterError, RouterModel


class LlmModelConflictError(Exception):
    pass


class LlmModelNotFoundError(Exception):
    pass


class LlmModelActivationError(LlmRouterError):
    pass


@dataclass(frozen=True, slots=True)
class LlmModelSnapshot:
    models: list[RouterModel]
    selected_model: str
    loaded_model: str | None


class AdminLlmService:
    def __init__(
        self,
        session: AsyncSession,
        router: LlmRouterClient,
        *,
        fallback_model: str,
    ) -> None:
        self._session = session
        self._router = router
        self._fallback_model = fallback_model

    async def snapshot(self) -> LlmModelSnapshot:
        selected = await self.selected_model()
        models = await self._router.list_models()
        loaded = next((model.id for model in models if model.status == "loaded"), None)
        return LlmModelSnapshot(
            models=models, selected_model=selected, loaded_model=loaded
        )

    async def selected_model(self) -> str:
        async with self._session.begin():
            configuration = await get_llm_configuration_for_update(
                self._session, fallback_model=self._fallback_model
            )
            return configuration.selected_model

    async def download(self, raw_model: str) -> str:
        model_id = normalize_hf_model_reference(raw_model)
        async with self._session.begin():
            await lock_llm_configuration(self._session)
            models = await self._router.list_models()
            existing = next((item for item in models if item.id == model_id), None)
            if existing is not None and existing.status != "incomplete":
                raise LlmModelConflictError("Ce modèle est déjà connu du serveur LLM")
            await self._router.download(model_id)
        return model_id

    async def activate(self, raw_model: str) -> str:
        model_id = normalize_hf_model_reference(raw_model)
        async with self._session.begin():
            configuration = await get_llm_configuration_for_update(
                self._session, fallback_model=self._fallback_model
            )
            busy = await self._session.scalar(
                select(func.count(DocumentJob.id)).where(
                    DocumentJob.status.in_(
                        [DocumentJobStatus.PENDING, DocumentJobStatus.PROCESSING]
                    )
                )
            )
            if busy:
                raise LlmModelConflictError(
                    "Un modèle ne peut pas être changé tant que des générations "
                    "sont en attente ou en cours."
                )
            models = await self._router.list_models()
            target = next((item for item in models if item.id == model_id), None)
            if target is None or target.status in {"downloading", "incomplete"}:
                raise LlmModelNotFoundError(
                    "Le modèle n’est pas entièrement téléchargé"
                )
            previous_id = configuration.selected_model
            previous_loaded = next(
                (item.id for item in models if item.status == "loaded"), None
            )
            try:
                if previous_loaded and previous_loaded != model_id:
                    await self._router.unload(previous_loaded)
                if target.status != "loaded":
                    await self._router.load(model_id)
                    await self._router.wait_until_loaded(model_id)
            except LlmRouterError as load_error:
                if previous_loaded and previous_loaded != model_id:
                    try:
                        # Libère une instance cible encore en chargement avant
                        # de restaurer l'unique emplacement VRAM.
                        current = await self._router.list_models()
                        target_now = next(
                            (item for item in current if item.id == model_id), None
                        )
                        if target_now is not None and target_now.status in {
                            "loaded",
                            "loading",
                            "sleeping",
                        }:
                            await self._router.unload(model_id)
                        await self._router.load(previous_loaded)
                        await self._router.wait_until_loaded(previous_loaded)
                    except LlmRouterError as restore_error:
                        raise LlmModelActivationError(
                            "Le nouveau modèle n’a pas été activé et l’ancien "
                            "modèle n’a pas pu être restauré. Aucun changement "
                            "n’a été enregistré ; vérifiez l’état du Router."
                        ) from restore_error
                raise load_error
            configuration.selected_model = model_id
            return previous_id

    async def unload(self, raw_model: str) -> None:
        model_id = normalize_hf_model_reference(raw_model)
        async with self._session.begin():
            configuration = await get_llm_configuration_for_update(
                self._session, fallback_model=self._fallback_model
            )
            busy = await self._session.scalar(
                select(func.count(DocumentJob.id)).where(
                    DocumentJob.status == DocumentJobStatus.PROCESSING
                )
            )
            if busy:
                raise LlmModelConflictError("Une génération est en cours")
            if configuration.selected_model == model_id:
                raise LlmModelConflictError(
                    "Le modèle sélectionné ne peut pas être déchargé"
                )
            await self._router.unload(model_id)
