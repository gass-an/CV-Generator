import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from app.clients.avp_client import (
    AvpClientError,
    AvpData,
    AvpInvalidResponseError,
    AvpNotFoundError,
)
from app.clients.llm_client import (
    LlmClientError,
    LlmInvalidResponseError,
    LlmTimeoutError,
)
from app.models.document_job import DocumentType
from app.processors.cover_letter_document_processor import (
    CoverLetterDocumentProcessor,
)
from app.processors.document_processor import DocumentJobData, DocumentProcessingError

AVP = AvpData(
    reference="3134-26-1382/SR",
    content="# Missions\n- Conduite de projet",
    source_url="https://opt.example/index.md",
    is_archived=False,
)
RESUME = {"skills": [{"name": "Python"}]}


class FakeAvpClient:
    def __init__(self, result: AvpData | Exception) -> None:
        self.result = result
        self.requested_number: str | None = None

    async def get_avp(self, avp_number: str) -> AvpData:
        self.requested_number = avp_number
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


def make_job() -> DocumentJobData:
    return DocumentJobData(
        id=uuid.uuid4(),
        document_type=DocumentType.COVER_LETTER,
        avp_number=AVP.reference,
        resume_data=RESUME,
        started_at=datetime.now(UTC),
    )


def make_processor(
    *,
    avp_result: AvpData | Exception = AVP,
    llm_result: str | Exception = "= Lettre de motivation\n\nContenu factuel.",
) -> tuple[CoverLetterDocumentProcessor, FakeAvpClient, RecordingPromptBuilder]:
    avp_client = FakeAvpClient(avp_result)
    builder = RecordingPromptBuilder()
    processor = CoverLetterDocumentProcessor(
        avp_client=avp_client,  # type: ignore[arg-type]
        prompt_builder=builder,  # type: ignore[arg-type]
        llm_client=FakeLlmClient(llm_result),  # type: ignore[arg-type]
    )
    return processor, avp_client, builder


@pytest.mark.asyncio
async def test_process_returns_asciidoc_and_keeps_sources_separate() -> None:
    processor, avp_client, builder = make_processor()

    result = await processor.process(make_job())

    assert result.format == "asciidoc"
    assert result.content.startswith("= Lettre de motivation")
    assert avp_client.requested_number == AVP.reference
    assert builder.resume_data is RESUME
    assert builder.avp is AVP
    assert "Conduite de projet" not in str(builder.resume_data)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "code"),
    [
        (AvpNotFoundError(), "avp_not_found"),
        (AvpInvalidResponseError(), "avp_invalid_response"),
        (AvpClientError(), "avp_source_error"),
    ],
)
async def test_process_maps_avp_errors(error: Exception, code: str) -> None:
    processor, _, _ = make_processor(avp_result=error)
    with pytest.raises(DocumentProcessingError) as caught:
        await processor.process(make_job())
    assert caught.value.code == code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "code"),
    [
        (LlmTimeoutError(), "llm_timeout"),
        (LlmClientError(), "llm_api_error"),
        (LlmInvalidResponseError(), "llm_invalid_response"),
    ],
)
async def test_process_maps_llm_errors(error: Exception, code: str) -> None:
    processor, _, _ = make_processor(llm_result=error)
    with pytest.raises(DocumentProcessingError) as caught:
        await processor.process(make_job())
    assert caught.value.code == code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    ["", "   ", "```asciidoc\n= Lettre de motivation\n```"],
)
async def test_process_rejects_invalid_generated_document(content: str) -> None:
    processor, _, _ = make_processor(llm_result=content)
    with pytest.raises(DocumentProcessingError) as caught:
        await processor.process(make_job())
    assert caught.value.code == "invalid_generated_document"
