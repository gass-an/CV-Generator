import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.models.document_job import DocumentJobStatus


class CreateCvDocumentRequest(BaseModel):
    avp_number: str = Field(min_length=1, max_length=128)
    resume: dict[str, Any]

    @field_validator("avp_number")
    @classmethod
    def validate_avp_number(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("avp_number must not be empty")
        return normalized


class DocumentJobCreatedResponse(BaseModel):
    id: uuid.UUID
    status: DocumentJobStatus


class DocumentJobStatusResponse(BaseModel):
    id: uuid.UUID
    status: DocumentJobStatus
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class DocumentResultResponse(BaseModel):
    id: uuid.UUID
    type: Literal["cv"]
    format: str
    content: str


class ErrorDetail(BaseModel):
    code: str
    message: str
