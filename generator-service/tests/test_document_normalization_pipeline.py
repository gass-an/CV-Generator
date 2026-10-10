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


class FakeAvpClient:
    async def get_avp(self, avp_number: str) -> AvpData:
        return AVP


class FakePromptBuilder:
    def build(
        self, *, resume_data: dict[str, Any], avp: AvpData
    ) -> list[dict[str, str]]:
        return [{"role": "user", "content": "test"}]


class MarkdownLlmClient:
    async def generate(self, messages: list[dict[str, str]]) -> str:
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
        started_at=datetime.now(UTC),
    )

    result = await processor.process(job)

    assert result.format == "asciidoc"
    assert result.content == "= Document\n\n* *Élément :* contenu\n** Détail"
