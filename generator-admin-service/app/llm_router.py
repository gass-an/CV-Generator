import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx


class LlmRouterError(Exception):
    """Erreur publique et non sensible liée au Router llama.cpp."""


class LlmRouterUnavailableError(LlmRouterError):
    pass


class LlmRouterInvalidResponseError(LlmRouterError):
    pass


class LlmRouterLoadTimeoutError(LlmRouterError):
    pass


class LlmRouterUnloadTimeoutError(LlmRouterError):
    pass


@dataclass(frozen=True, slots=True)
class RouterModel:
    id: str
    status: str
    size: int | None
    progress_done: int | None
    progress_total: int | None
    failed: bool

    @property
    def quantization(self) -> str | None:
        return self.id.rsplit(":", 1)[1] if ":" in self.id else None


class LlmRouterClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout: float,
        activation_timeout: float,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = http_client or httpx.AsyncClient(timeout=timeout)
        self._activation_timeout = activation_timeout

    async def list_models(self) -> list[RouterModel]:
        payload = await self._request_json("GET", "/models")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise LlmRouterInvalidResponseError("Réponse invalide du serveur LLM")
        return [self._parse_model(item) for item in data]

    async def download(self, model: str) -> None:
        await self._request_success("POST", "/models", json={"model": model})

    async def load(self, model: str) -> None:
        await self._request_success(
            "POST",
            "/models/load",
            json={"model": model},
            timeout=self._activation_timeout,
        )

    async def wait_until_loaded(
        self,
        model: str,
        *,
        poll_interval: float = 0.5,
    ) -> None:
        """Attend la confirmation asynchrone du Router après `/models/load`."""
        deadline = time.monotonic() + self._activation_timeout
        observed = False
        while True:
            models = await self.list_models()
            target = next((item for item in models if item.id == model), None)
            if target is None:
                raise LlmRouterError("Le modèle a disparu du serveur LLM")
            if target.status == "loaded":
                return
            if target.failed:
                raise LlmRouterError("Le chargement du modèle a échoué")
            if observed and target.status not in {"loading", "sleeping"}:
                raise LlmRouterError(
                    f"Le chargement du modèle s’est arrêté à l’état {target.status}"
                )
            observed = observed or target.status == "loading"
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LlmRouterLoadTimeoutError(
                    "Le chargement du modèle n’a pas été confirmé avant le délai"
                )
            await asyncio.sleep(min(poll_interval, remaining))

    async def unload(self, model: str) -> None:
        await self._request_success("POST", "/models/unload", json={"model": model})

    async def wait_until_unloaded(
        self,
        model: str,
        *,
        poll_interval: float = 0.5,
    ) -> None:
        """Attend que le processus enfant du modèle soit effectivement arrêté."""
        deadline = time.monotonic() + self._activation_timeout
        while True:
            models = await self.list_models()
            target = next((item for item in models if item.id == model), None)
            if target is None:
                raise LlmRouterError("Le modèle a disparu du serveur LLM")
            if target.status == "unloaded":
                return
            if target.status not in {"loaded", "loading", "sleeping"}:
                raise LlmRouterError(
                    f"Le déchargement du modèle s’est arrêté à l’état {target.status}"
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LlmRouterUnloadTimeoutError(
                    "Le déchargement du modèle n’a pas été confirmé avant le délai"
                )
            await asyncio.sleep(min(poll_interval, remaining))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request_json(self, method: str, path: str, **kwargs: Any) -> object:
        try:
            response = await self._client.request(
                method, f"{self._base_url}{path}", **kwargs
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as error:
            raise LlmRouterUnavailableError(
                "Le serveur LLM n’a pas répondu avant le délai autorisé"
            ) from error
        except httpx.RequestError as error:
            # RequestError couvre les erreurs de transport HTTPX (connexion,
            # protocole distant, lecture, etc.) sans masquer les erreurs de code.
            raise LlmRouterUnavailableError(
                "Le serveur LLM est indisponible"
            ) from error
        except httpx.HTTPStatusError as error:
            raise LlmRouterError(
                "L’opération a été refusée par le serveur LLM"
            ) from error
        except ValueError as error:
            raise LlmRouterInvalidResponseError(
                "Réponse invalide du serveur LLM"
            ) from error

    async def _request_success(self, method: str, path: str, **kwargs: Any) -> None:
        payload = await self._request_json(method, path, **kwargs)
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise LlmRouterInvalidResponseError(
                "Le serveur LLM n’a pas confirmé l’opération"
            )

    @staticmethod
    def _parse_model(item: object) -> RouterModel:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise LlmRouterInvalidResponseError("Modèle LLM invalide dans la réponse")
        status_data = item.get("status")
        status_data = status_data if isinstance(status_data, dict) else {}
        status_value = status_data.get("value", "unloaded")
        if not isinstance(status_value, str):
            status_value = "error"
        progress = status_data.get("progress")
        done = total = None
        if isinstance(progress, dict):
            transfers = [v for v in progress.values() if isinstance(v, dict)]
            done_values = [v.get("done") for v in transfers]
            total_values = [v.get("total") for v in transfers]
            if transfers and all(isinstance(v, int) for v in done_values):
                done = sum(done_values)
            if transfers and all(isinstance(v, int) and v > 0 for v in total_values):
                total = sum(total_values)
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        size = meta.get("size")
        return RouterModel(
            id=item["id"],
            status=status_value,
            size=size if isinstance(size, int) else total,
            progress_done=done,
            progress_total=total,
            failed=status_data.get("failed") is True,
        )
