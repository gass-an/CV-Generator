from app.processors.cover_letter_document_processor import CoverLetterDocumentProcessor
from app.processors.cv_document_processor import CvDocumentProcessor
from app.processors.document_processor import (
    DocumentJobData,
    DocumentProcessingError,
    DocumentProcessor,
    GeneratedDocument,
)

__all__ = [
    "DocumentJobData",
    "DocumentProcessingError",
    "DocumentProcessor",
    "GeneratedDocument",
    "CvDocumentProcessor",
    "CoverLetterDocumentProcessor",
]
