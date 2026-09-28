import uuid


class GeneratorServiceError(Exception):
    """Base exception for expected service errors."""


class DocumentJobNotFoundError(GeneratorServiceError):
    def __init__(self, job_id: uuid.UUID) -> None:
        super().__init__(f"Document job {job_id} was not found")


class DocumentJobNotReadyError(GeneratorServiceError):
    """Raised when a document result is requested before completion."""


class DocumentGenerationFailedError(GeneratorServiceError):
    """Raised when a failed job's result is requested."""


class DocumentResultUnavailableError(GeneratorServiceError):
    """Raised when a completed job has no usable AsciiDoc result."""
