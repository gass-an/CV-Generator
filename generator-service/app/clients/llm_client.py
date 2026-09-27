from typing import TypedDict

import httpx


class ChatMessage(TypedDict):
    role: str
    content: str


class LlmClientError(Exception):
    """Base error raised while calling the OpenAI-compatible API."""


class LlmTimeoutError(LlmClientError):
    """The LLM did not answer before the configured timeout."""


class LlmInvalidResponseError(LlmClientError):
    """The LLM returned an unusable response."""


class LlmClient:
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
        try:
            response = await self._http_client.post(
                f"{self._base_url}/v1/chat/completions",
                json={"model": self._model, "messages": messages, "stream": False},
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise LlmTimeoutError("LLM request timed out") from error
        except httpx.HTTPError as error:
            raise LlmClientError("LLM API request failed") from error

        try:
            payload = response.json()
        except ValueError as error:
            raise LlmInvalidResponseError("LLM response is not valid JSON") from error
        if not isinstance(payload, dict):
            raise LlmInvalidResponseError("LLM response has an invalid structure")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LlmInvalidResponseError("LLM response contains no choices")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise LlmInvalidResponseError("LLM response contains no message")
        if choice.get("finish_reason") == "length":
            raise LlmInvalidResponseError("LLM response was truncated")
        if not isinstance(choice.get("message"), dict):
            raise LlmInvalidResponseError("LLM response contains no message")
        content = choice["message"].get("content")
        if not isinstance(content, str) or not content.strip():
            raise LlmInvalidResponseError("LLM response content is empty")
        return content.strip()

    async def aclose(self) -> None:
        await self._http_client.aclose()
