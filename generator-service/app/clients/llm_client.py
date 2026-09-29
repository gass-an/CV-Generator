from typing import TypedDict

import httpx


class ChatMessage(TypedDict):
    """Message transmis à l'API de conversation compatible OpenAI."""

    role: str
    content: str


class LlmClientError(Exception):
    """Erreur générique lors d'un appel à l'API compatible OpenAI."""


class LlmTimeoutError(LlmClientError):
    """Le LLM n'a pas répondu avant le délai configuré."""


class LlmInvalidResponseError(LlmClientError):
    """Le LLM a retourné une réponse inexploitable."""


class LlmClient:
    """Appelle l'endpoint de conversation OpenAI exposé par llama.cpp."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: float,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._http_client = http_client or httpx.AsyncClient(timeout=timeout)

    async def generate(self, messages: list[ChatMessage]) -> str:
        """Génère un contenu textuel et valide la structure minimale de la réponse."""
        try:
            response = await self._http_client.post(
                f"{self._base_url}/v1/chat/completions",
                json={"model": self._model, "messages": messages, "stream": False},
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise LlmTimeoutError(
                "La requête vers le LLM a dépassé le délai autorisé"
            ) from error
        except httpx.HTTPError as error:
            raise LlmClientError("La requête vers l'API du LLM a échoué") from error

        try:
            payload = response.json()
        except ValueError as error:
            raise LlmInvalidResponseError(
                "La réponse du LLM n'est pas un JSON valide"
            ) from error
        if not isinstance(payload, dict):
            raise LlmInvalidResponseError("La réponse du LLM a une structure invalide")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LlmInvalidResponseError("La réponse du LLM ne contient aucun choix")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise LlmInvalidResponseError("La réponse du LLM ne contient aucun message")
        if choice.get("finish_reason") == "length":
            raise LlmInvalidResponseError("La réponse du LLM a été tronquée")
        if not isinstance(choice.get("message"), dict):
            raise LlmInvalidResponseError("La réponse du LLM ne contient aucun message")
        content = choice["message"].get("content")
        if not isinstance(content, str) or not content.strip():
            raise LlmInvalidResponseError("Le contenu de la réponse du LLM est vide")
        return content.strip()

    async def aclose(self) -> None:
        await self._http_client.aclose()
