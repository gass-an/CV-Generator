import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from app.clients.avp_client import AvpClientError, AvpData, AvpNotFoundError
from app.clients.llm_client import LlmClientError, LlmTimeoutError
from app.models.document_job import DocumentType
from app.processors.document_processor import DocumentJobData, DocumentProcessingError
from app.processors.interview_prep_document_processor import (
    InterviewPrepDocumentProcessor,
)

AVP = AvpData(
    reference="REST-2026-014",
    content="# Responsable de salle\n- Organiser le service",
    source_url="https://opt.example/index.md",
    is_archived=False,
)
RESUME = {"skills": [{"name": "Service en salle"}]}


class FakeAvpClient:
    def __init__(self, result: AvpData | Exception) -> None:
        self.result = result

    async def get_avp(self, avp_number: str) -> AvpData:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class RecordingPromptBuilder:
    def __init__(self) -> None:
        self.resume_data: dict[str, Any] | None = None
        self.avp: AvpData | None = None

    def build(
        self, *, resume_data: dict[str, Any], avp: AvpData
    ) -> list[dict[str, str]]:
        self.resume_data = resume_data
        self.avp = avp
        return [{"role": "user", "content": "sources séparées"}]


class FakeLlmClient:
    def __init__(self, result: str | Exception) -> None:
        self.result = result

    async def generate(self, messages: list[dict[str, str]]) -> str:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def make_job(
    document_type: DocumentType = DocumentType.INTERVIEW_PREP,
) -> DocumentJobData:
    return DocumentJobData(
        id=uuid.uuid4(),
        document_type=document_type,
        avp_number=AVP.reference,
        resume_data=RESUME,
        started_at=datetime.now(UTC),
    )


def make_processor(
    avp_result: AvpData | Exception = AVP,
    llm_result: str | Exception = "= Guide de préparation à l'entretien\n\nContenu",
) -> tuple[InterviewPrepDocumentProcessor, RecordingPromptBuilder]:
    builder = RecordingPromptBuilder()
    processor = InterviewPrepDocumentProcessor(
        avp_client=FakeAvpClient(avp_result),  # type: ignore[arg-type]
        prompt_builder=builder,  # type: ignore[arg-type]
        llm_client=FakeLlmClient(llm_result),  # type: ignore[arg-type]
    )
    return processor, builder


@pytest.mark.asyncio
async def test_process_generates_asciidoc_and_passes_both_sources() -> None:
    processor, builder = make_processor()

    result = await processor.process(make_job())

    assert result.format == "asciidoc"
    assert result.content.startswith("= Guide de préparation")
    assert builder.resume_data is RESUME
    assert builder.avp is AVP


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "code"),
    [
        (AvpNotFoundError(), "avp_not_found"),
        (AvpClientError(), "avp_source_error"),
        (LlmTimeoutError(), "llm_timeout"),
        (LlmClientError(), "llm_api_error"),
    ],
)
async def test_process_maps_avp_and_llm_errors(error: Exception, code: str) -> None:
    if isinstance(error, AvpClientError):
        processor, _ = make_processor(avp_result=error)
    else:
        processor, _ = make_processor(llm_result=error)

    with pytest.raises(DocumentProcessingError) as caught:
        await processor.process(make_job())
    assert caught.value.code == code


@pytest.mark.asyncio
async def test_process_rejects_wrong_document_type() -> None:
    processor, _ = make_processor()
    with pytest.raises(DocumentProcessingError) as caught:
        await processor.process(make_job(DocumentType.CV))
    assert caught.value.code == "unsupported_document_type"
