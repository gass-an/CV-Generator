from app.models.document_job import DocumentType
from app.processors.document_processor import AvpLlmDocumentProcessor


class CvDocumentProcessor(AvpLlmDocumentProcessor):
    """Génère un CV AsciiDoc adapté à un AVP exact."""

    document_type = DocumentType.CV
