from app.models.document_job import DocumentType
from app.processors.document_processor import AvpLlmDocumentProcessor


class CoverLetterDocumentProcessor(AvpLlmDocumentProcessor):
    """Génère une lettre de motivation AsciiDoc adaptée à un AVP exact."""

    document_type = DocumentType.COVER_LETTER
