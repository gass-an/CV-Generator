import asyncio
import logging
from dataclasses import dataclass, replace
from pathlib import Path

from cv_generator_shared.document_jobs import DocumentJob, DocumentJobStatus
from cv_generator_shared.llm import (
    get_llm_configuration_for_update,
    lock_llm_configuration,
    normalize_hf_model_reference,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm_metadata import inspect_model
from app.llm_router import LlmRouterClient, LlmRouterError, RouterModel

logger = logging.getLogger(__name__)


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
        cache_path: str = "/models",
        context_size: int = 8192,
        gpu_layers: int = 99,
    ) -> None:
        self._session = session
        self._router = router
        self._fallback_model = fallback_model
        self._cache_path = Path(cache_path)
        self._context_size = context_size
        self._gpu_layers = gpu_layers

    async def snapshot(self) -> LlmModelSnapshot:
        selected = await self.selected_model()
        models = await self._router.list_models()
        models = await asyncio.to_thread(self._with_local_metadata, models)
        loaded = next(
            (model.id for model in models if model.status in {"loaded", "sleeping"}),
            None,
        )
        return LlmModelSnapshot(
            models=models, selected_model=selected, loaded_model=loaded
        )

    def _with_local_metadata(self, models: list[RouterModel]) -> list[RouterModel]:
        enriched = []
        for model in models:
            local = inspect_model(
                model.path,
                cache_root=self._cache_path,
                context_size=self._context_size,
                gpu_layers=self._gpu_layers,
                cache_unavailable=model.status not in {"downloading", "incomplete"},
            )
            enriched.append(
                replace(
                    model,
                    size=(
                        local.size_bytes if local.size_bytes is not None else model.size
                    ),
                    vram_estimate=local.vram_estimate_bytes,
                )
            )
        return enriched

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
            previous_active = next(
                (
                    item
                    for item in models
                    if item.status in {"loaded", "loading", "sleeping"}
                ),
                None,
            )
            try:
                if previous_active and previous_active.id != model_id:
                    logger.info(
                        "Déchargement du modèle LLM actuel model=%s target=%s",
                        previous_active.id,
                        model_id,
                    )
                    await self._unload_and_wait(previous_active.id)
                    logger.info(
                        "Déchargement du modèle LLM confirmé model=%s",
                        previous_active.id,
                    )
                await self._ensure_model_ready(target)
            except LlmRouterError as load_error:
                logger.warning(
                    "Échec de la bascule du modèle LLM target=%s previous=%s cause=%s",
                    model_id,
                    previous_active.id if previous_active else None,
                    type(load_error).__name__,
                    exc_info=True,
                )
                if previous_active and previous_active.id != model_id:
                    try:
                        await self._prepare_rollback(model_id, previous_active.id)
                        restored_status, preserved = await self._restore_previous(
                            previous_active.id
                        )
                        logger.info(
                            "Restauration du modèle LLM confirmée model=%s état=%s",
                            previous_active.id,
                            restored_status,
                        )
                    except LlmRouterError as restore_error:
                        state = await self._observed_router_state()
                        logger.error(
                            "Échec de restauration du modèle LLM model=%s "
                            "target=%s cause=%s state=%s",
                            previous_active.id,
                            model_id,
                            type(restore_error).__name__,
                            state,
                            exc_info=True,
                        )
                        raise LlmModelActivationError(
                            "Le nouveau modèle n’a pas été activé et l’ancien "
                            "modèle n’a pas pu être restauré. Aucun changement "
                            f"n’a été enregistré. Au dernier contrôle : {state}."
                        ) from restore_error
                    raise LlmModelActivationError(
                        "Le nouveau modèle n’a pas été activé ; l’ancien modèle "
                        "était déjà chargé et a été conservé. La sélection "
                        "précédente est conservée."
                        if preserved and restored_status == "loaded"
                        else (
                            "Le nouveau modèle n’a pas été activé ; l’ancien "
                            "modèle restait actif et a été conservé. La sélection "
                            "précédente est conservée."
                            if preserved and restored_status == "sleeping"
                            else "Le nouveau modèle n’a pas été activé ; l’ancien "
                            "modèle a été restauré. La sélection précédente est "
                            "conservée."
                        )
                    ) from load_error
                raise load_error
            configuration.selected_model = model_id
            return previous_id

    async def _ensure_model_ready(self, model: RouterModel) -> str:
        """Confirme l'état prêt sans répéter une opération déjà en cours."""
        if model.status in {"loaded", "sleeping"}:
            if model.status == "sleeping":
                # b11889 garde le processus enfant vivant en sleeping et le
                # réveille sur la prochaine requête. `/models/load` refuse
                # alors l'opération car l'instance est déjà en cours.
                logger.info(
                    "Modèle LLM déjà actif à l’état sleeping model=%s",
                    model.id,
                )
            return model.status
        if model.status == "loading":
            logger.info("Attente du chargement LLM déjà en cours model=%s", model.id)
            await self._router.wait_until_loaded(model.id)
            return "loaded"
        if model.status == "unloaded":
            logger.info("Chargement du modèle LLM target=%s", model.id)
            await self._router.load(model.id)
            await self._router.wait_until_loaded(model.id)
            logger.info("Chargement du modèle LLM confirmé target=%s", model.id)
            return "loaded"
        raise LlmRouterError(
            f"Le modèle ne peut pas être activé depuis l’état {model.status}"
        )

    async def _prepare_rollback(self, target_id: str, previous_id: str) -> None:
        """Libère l'unique slot Router avant de restaurer l'ancien modèle."""
        current = await self._router.list_models()
        target = next((item for item in current if item.id == target_id), None)
        if target is not None and target.status in {"loaded", "loading", "sleeping"}:
            logger.info("Nettoyage du modèle LLM cible target=%s", target_id)
            await self._unload_and_wait(target_id)

        current = await self._router.list_models()
        previous = next((item for item in current if item.id == previous_id), None)
        if previous is None:
            raise LlmRouterError("L’ancien modèle a disparu du serveur LLM")
        if previous.status not in {"loaded", "loading", "sleeping", "unloaded"}:
            raise LlmRouterError(
                "L’ancien modèle ne peut pas être restauré depuis l’état "
                f"{previous.status}"
            )

    async def _restore_previous(self, model_id: str) -> tuple[str, bool]:
        current = await self._router.list_models()
        previous = next((item for item in current if item.id == model_id), None)
        if previous is None:
            raise LlmRouterError("L’ancien modèle a disparu du serveur LLM")
        if previous.status in {"loaded", "sleeping"}:
            return previous.status, True
        return await self._ensure_model_ready(previous), False

    async def _unload_and_wait(self, model_id: str) -> None:
        try:
            await self._router.unload(model_id)
        except LlmRouterError:
            # Le moniteur peut publier `unloaded` entre le GET et le POST. Dans
            # ce seul cas, le refus "not running" confirme déjà le résultat.
            current = await self._router.list_models()
            model = next((item for item in current if item.id == model_id), None)
            if model is None or model.status != "unloaded":
                raise
            return
        await self._router.wait_until_unloaded(model_id)

    async def _observed_router_state(self) -> str:
        try:
            models = await self._router.list_models()
        except LlmRouterError:
            return "l’état du Router est indisponible"
        active = [
            f"{item.id} ({item.status})"
            for item in models
            if item.status in {"loaded", "loading", "sleeping"}
        ]
        if not active:
            return "aucun modèle n’est chargé"
        return "instance active " + ", ".join(active)

    async def unload(self, raw_model: str) -> None:
        model_id = normalize_hf_model_reference(raw_model)
        async with self._session.begin():
            await get_llm_configuration_for_update(
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
                raise LlmModelConflictError("Une génération est en cours")
            models = await self._router.list_models()
            target = next((item for item in models if item.id == model_id), None)
            if target is None:
                raise LlmModelNotFoundError("Le modèle est introuvable")
            if target.status == "unloaded":
                return
            await self._unload_and_wait(model_id)
