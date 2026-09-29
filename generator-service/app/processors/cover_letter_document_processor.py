from app.models.document_job import DocumentType
from app.processors.document_processor import AvpLlmDocumentProcessor


class CoverLetterDocumentProcessor(AvpLlmDocumentProcessor):
    document_type = DocumentType.COVER_LETTER
