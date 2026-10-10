from app.models.document_job import DocumentType
from app.processors.document_processor import AvpLlmDocumentProcessor


class InterviewPrepDocumentProcessor(AvpLlmDocumentProcessor):
    """Génère un guide AsciiDoc de préparation à un entretien ciblé."""

    document_type = DocumentType.INTERVIEW_PREP
