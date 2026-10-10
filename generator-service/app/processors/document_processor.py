import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.asciidoc import normalize_asciidoc
from app.clients.avp_client import (
    AvpClient,
    AvpClientError,
    AvpData,
    AvpInvalidResponseError,
    AvpNotFoundError,
)
from app.clients.llm_client import (
    ChatMessage,
    LlmClient,
    LlmClientError,
    LlmInvalidResponseError,
    LlmTimeoutError,
)
from app.models.document_job import DocumentType


@dataclass(frozen=True, slots=True)
class DocumentJobData:
    """Copie détachée des données nécessaires au traitement d'un job."""

    id: uuid.UUID
    document_type: DocumentType
    avp_number: str
    resume_data: dict[str, Any]
    started_at: datetime


@dataclass(frozen=True, slots=True)
class GeneratedDocument:
    """Résultat textuel normalisé produit par un processor."""

    content: str
    format: str


class DocumentProcessingError(Exception):
    """Erreur contrôlée associée à un code technique persistant."""

    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DocumentProcessor(Protocol):
    """Contrat commun des processors de documents."""

    async def process(self, job: DocumentJobData) -> GeneratedDocument: ...


class DocumentPromptBuilder(Protocol):
    """Construit les messages LLM en gardant séparées les sources non fiables."""

    def build(
        self, *, resume_data: dict[str, Any], avp: AvpData
    ) -> list[ChatMessage]: ...


FENCED_DOCUMENT = re.compile(
    r"\A\s*```[^\r\n]*\r?\n.*\r?\n```\s*\Z",
    flags=re.DOTALL,
)


class AvpLlmDocumentProcessor:
    """Pipeline commun de récupération AVP, génération LLM et validation."""

    document_type: DocumentType

    def __init__(
        self,
        *,
        avp_client: AvpClient,
        prompt_builder: DocumentPromptBuilder,
        llm_client: LlmClient,
    ) -> None:
        self._avp_client = avp_client
        self._prompt_builder = prompt_builder
        self._llm_client = llm_client

    async def process(self, job: DocumentJobData) -> GeneratedDocument:
        if job.document_type is not self.document_type:
            raise DocumentProcessingError(
                code="unsupported_document_type",
                message="Type de document non pris en charge",
            )
        try:
            avp = await self._avp_client.get_avp(job.avp_number)
        except AvpNotFoundError as error:
            raise DocumentProcessingError(
                code="avp_not_found", message="AVP introuvable"
            ) from error
        except AvpInvalidResponseError as error:
            raise DocumentProcessingError(
                code="avp_invalid_response",
                message="Réponse invalide de la source AVP",
            ) from error
        except AvpClientError as error:
            raise DocumentProcessingError(
                code="avp_source_error", message="La source AVP est indisponible"
            ) from error

        messages = self._prompt_builder.build(resume_data=job.resume_data, avp=avp)
        try:
            generated_content = await self._llm_client.generate(messages)
        except LlmTimeoutError as error:
            raise DocumentProcessingError(
                code="llm_timeout",
                message="La requête vers le LLM a dépassé le délai autorisé",
            ) from error
        except LlmInvalidResponseError as error:
            raise DocumentProcessingError(
                code="llm_invalid_response", message="Réponse invalide du LLM"
            ) from error
        except LlmClientError as error:
            raise DocumentProcessingError(
                code="llm_api_error", message="La requête vers l'API du LLM a échoué"
            ) from error

        if not isinstance(generated_content, str) or not generated_content.strip():
            raise DocumentProcessingError(
                code="invalid_generated_document",
                message="Le document généré est vide",
            )
        generated_content = normalize_asciidoc(generated_content)
        if FENCED_DOCUMENT.fullmatch(generated_content):
            raise DocumentProcessingError(
                code="invalid_generated_document",
                message="Le document généré possède un format invalide",
            )
        return GeneratedDocument(content=generated_content, format="asciidoc")
