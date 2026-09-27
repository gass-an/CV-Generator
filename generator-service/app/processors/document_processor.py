import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.models.document_job import DocumentType


@dataclass(frozen=True, slots=True)
class DocumentJobData:
    id: uuid.UUID
    document_type: DocumentType
    avp_number: str
    resume_data: dict[str, Any]
    started_at: datetime


@dataclass(frozen=True, slots=True)
class GeneratedDocument:
    content: str
    format: str


class DocumentProcessingError(Exception):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DocumentProcessor(Protocol):
    async def process(self, job: DocumentJobData) -> GeneratedDocument: ...
