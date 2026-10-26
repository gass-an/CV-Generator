import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from app.clients.avp_client import AvpData
from app.models.document_job import DocumentType
from app.processors.cover_letter_document_processor import (
    CoverLetterDocumentProcessor,
)
from app.processors.cv_document_processor import CvDocumentProcessor
from app.processors.document_processor import DocumentJobData
from app.processors.interview_prep_document_processor import (
    InterviewPrepDocumentProcessor,
)

AVP = AvpData(
    reference="TEST-001",
    content="# Poste\n- Mission",
    source_url="https://opt.example/index.md",
    is_archived=False,
)
REFERENCE_TIME = datetime(2026, 10, 17, 1, 30, tzinfo=UTC)


class FakeAvpClient:
    async def get_avp(self, avp_number: str) -> AvpData:
        return AVP


class FakePromptBuilder:
    def build(
        self, *, resume_data: dict[str, Any], avp: AvpData
    ) -> list[dict[str, str]]:
        return [{"role": "user", "content": "test"}]


class MarkdownLlmClient:
    async def generate(self, messages: list[dict[str, str]], *, model: str) -> str:
        assert model
        return "# Document\n\n- **Élément :** contenu\n  - Détail  "


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("document_type", "processor_class"),
    [
        (DocumentType.CV, CvDocumentProcessor),
        (DocumentType.COVER_LETTER, CoverLetterDocumentProcessor),
        (DocumentType.INTERVIEW_PREP, InterviewPrepDocumentProcessor),
    ],
)
async def test_all_document_processors_store_normalized_asciidoc(
    document_type: DocumentType, processor_class: type
) -> None:
    processor = processor_class(
        avp_client=FakeAvpClient(),
        prompt_builder=FakePromptBuilder(),
        llm_client=MarkdownLlmClient(),
    )
    job = DocumentJobData(
        id=uuid.uuid4(),
        document_type=document_type,
        avp_number=AVP.reference,
        resume_data={"basics": {}},
        started_at=REFERENCE_TIME,
        llm_model="test/model-GGUF:Q4_K_M",
    )

    result = await processor.process(job)

    assert result.format == "asciidoc"
    expected_content = "= Document\n\n* *Élément :* contenu\n** Détail"
    if document_type is DocumentType.COVER_LETTER:
        expected_content = (
            "= Document\n\n"
            "Objet : Candidature à l'offre n° TEST-001\n\n"
            "* *Élément :* contenu\n"
            "** Détail"
        )
    assert result.content == expected_content
