import uuid
from datetime import UTC, datetime
from io import BytesIO
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
    include_offer_reference_in_subject,
)
from app.processors.document_processor import DocumentJobData, DocumentProcessingError
from app.renderers import DocxRenderer
from docx import Document

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
async def test_process_adds_offer_reference_to_subject() -> None:
    processor, _, _ = make_processor(
        llm_result=(
            "= Lettre de motivation\n\n"
            "Objet : Candidature au poste d'administrateur\n\nMadame, Monsieur,"
        )
    )

    result = await processor.process(make_job())

    assert (
        "Objet : Candidature à l'offre n° 3134-26-1382/SR – administrateur"
        in result.content
    )
    rendered_docx = Document(BytesIO(DocxRenderer().render(result.content)))
    assert any(
        paragraph.text
        == "Objet : Candidature à l'offre n° 3134-26-1382/SR – administrateur"
        for paragraph in rendered_docx.paragraphs
    )


def test_subject_is_unchanged_without_offer_reference() -> None:
    content = "= Lettre de motivation\n\nObjet : Candidature spontanée"

    assert include_offer_reference_in_subject(content, "  ") == content


def test_subject_does_not_duplicate_existing_offer_reference() -> None:
    content = (
        "= Lettre de motivation\n\n"
        "*Objet :* Candidature à l'offre n° 3134-26-1382/SR – Administrateur"
    )

    result = include_offer_reference_in_subject(content, "3134-26-1382/SR")

    assert result == content
    assert result.count("3134-26-1382/SR") == 1


def test_missing_subject_is_inserted_without_inventing_title() -> None:
    content = (
        "= Lettre de motivation\n\n"
        "Camille Exemple\n"
        "camille@example.nc\n\n"
        "Madame, Monsieur,\n\n"
        "Je vous adresse ma candidature."
    )

    result = include_offer_reference_in_subject(content, "3134-26-1382/SR")

    assert result == (
        "= Lettre de motivation\n\n"
        "Camille Exemple\n"
        "camille@example.nc\n\n"
        "Objet : Candidature à l'offre n° 3134-26-1382/SR\n\n"
        "Madame, Monsieur,\n\n"
        "Je vous adresse ma candidature."
    )
    assert "administrateur" not in result.casefold()


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
