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
from app.processors.cv_document_processor import CvDocumentProcessor
from app.processors.document_processor import DocumentJobData, DocumentProcessingError


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
        self,
        *,
        resume_data: dict[str, Any],
        avp: AvpData,
    ) -> list[dict[str, str]]:
        self.resume_data = resume_data
        self.avp = avp
        return [{"role": "user", "content": "separate data"}]


class FakeLlmClient:
    def __init__(self, result: str | Exception) -> None:
        self.result = result
        self.messages: list[dict[str, str]] | None = None

    async def generate(self, messages: list[dict[str, str]]) -> str:
        self.messages = messages
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


AVP = AvpData(
    reference="3134-26-1382/SR",
    content="# Compétences attendues\n- Conduite de projet",
    source_url="https://opt.example/index.md",
    is_archived=False,
)


def make_job(document_type: DocumentType = DocumentType.CV) -> DocumentJobData:
    return DocumentJobData(
        id=uuid.uuid4(),
        document_type=document_type,
        avp_number=AVP.reference,
        resume_data={"skills": [{"name": "Python"}]},
        started_at=datetime.now(UTC),
    )


def make_processor(
    *,
    avp_result: AvpData | Exception = AVP,
    llm_result: str | Exception = "= Camille Exemple\n\n== Compétences\n\n- Python",
) -> tuple[CvDocumentProcessor, RecordingPromptBuilder, FakeLlmClient]:
    builder = RecordingPromptBuilder()
    llm = FakeLlmClient(llm_result)
    processor = CvDocumentProcessor(
        avp_client=FakeAvpClient(avp_result),  # type: ignore[arg-type]
        prompt_builder=builder,  # type: ignore[arg-type]
        llm_client=llm,  # type: ignore[arg-type]
    )
    return processor, builder, llm


@pytest.mark.asyncio
async def test_process_returns_asciidoc_and_keeps_sources_separate() -> None:
    processor, builder, llm = make_processor()
    job = make_job()
    result = await processor.process(job)

    assert result.format == "asciidoc"
    assert result.content.startswith("= Camille Exemple")
    assert builder.resume_data is job.resume_data
    assert builder.resume_data == {"skills": [{"name": "Python"}]}
    assert builder.avp is AVP
    assert "Conduite de projet" not in str(builder.resume_data)
    assert llm.messages == [{"role": "user", "content": "separate data"}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("avp_error", "code"),
    [
        (AvpNotFoundError(), "avp_not_found"),
        (AvpClientError(), "avp_source_error"),
        (AvpInvalidResponseError(), "avp_invalid_response"),
    ],
)
async def test_process_maps_avp_errors(avp_error: Exception, code: str) -> None:
    processor, _, _ = make_processor(avp_result=avp_error)
    with pytest.raises(DocumentProcessingError) as caught:
        await processor.process(make_job())
    assert caught.value.code == code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("llm_error", "code"),
    [
        (LlmTimeoutError(), "llm_timeout"),
        (LlmInvalidResponseError(), "llm_invalid_response"),
        (LlmClientError(), "llm_api_error"),
    ],
)
async def test_process_maps_llm_errors(llm_error: Exception, code: str) -> None:
    processor, _, _ = make_processor(llm_result=llm_error)
    with pytest.raises(DocumentProcessingError) as caught:
        await processor.process(make_job())
    assert caught.value.code == code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        "",
        "   ",
        "```asciidoc\n= CV\n```",
        "```text\n= CV\n```",
        "```adoc\n= CV\n```",
    ],
)
async def test_process_rejects_invalid_generated_document(content: str) -> None:
    processor, _, _ = make_processor(llm_result=content)
    with pytest.raises(DocumentProcessingError) as caught:
        await processor.process(make_job())
    assert caught.value.code == "invalid_generated_document"


@pytest.mark.asyncio
async def test_process_allows_backticks_inside_document() -> None:
    content = "= CV\n\nUne valeur `technique` reste valide."
    processor, _, _ = make_processor(llm_result=content)
    result = await processor.process(make_job())
    assert result.content == content


@pytest.mark.asyncio
async def test_process_rejects_unsupported_document_type() -> None:
    job = make_job()
    job = DocumentJobData(
        id=job.id,
        document_type="letter",  # type: ignore[arg-type]
        avp_number=job.avp_number,
        resume_data=job.resume_data,
        started_at=job.started_at,
    )
    processor, _, _ = make_processor()
    with pytest.raises(DocumentProcessingError) as caught:
        await processor.process(job)
    assert caught.value.code == "unsupported_document_type"
