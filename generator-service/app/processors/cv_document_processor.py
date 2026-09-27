import re

from app.clients.avp_client import (
    AvpClient,
    AvpClientError,
    AvpInvalidResponseError,
    AvpNotFoundError,
)
from app.clients.llm_client import (
    LlmClient,
    LlmClientError,
    LlmInvalidResponseError,
    LlmTimeoutError,
)
from app.models.document_job import DocumentType
from app.processors.document_processor import (
    DocumentJobData,
    DocumentProcessingError,
    GeneratedDocument,
)
from app.prompts.cv_prompt_builder import CvPromptBuilder

FENCED_DOCUMENT = re.compile(
    r"\A\s*```[^\r\n]*\r?\n.*\r?\n```\s*\Z",
    flags=re.DOTALL,
)


class CvDocumentProcessor:
    def __init__(
        self,
        *,
        avp_client: AvpClient,
        prompt_builder: CvPromptBuilder,
        llm_client: LlmClient,
    ) -> None:
        self._avp_client = avp_client
        self._prompt_builder = prompt_builder
        self._llm_client = llm_client

    async def process(self, job: DocumentJobData) -> GeneratedDocument:
        if job.document_type is not DocumentType.CV:
            raise DocumentProcessingError(
                code="unsupported_document_type",
                message="Unsupported document type",
            )
        try:
            avp = await self._avp_client.get_avp(job.avp_number)
        except AvpNotFoundError as error:
            raise DocumentProcessingError(
                code="avp_not_found", message="AVP not found"
            ) from error
        except AvpInvalidResponseError as error:
            raise DocumentProcessingError(
                code="avp_invalid_response", message="Invalid AVP source response"
            ) from error
        except AvpClientError as error:
            raise DocumentProcessingError(
                code="avp_source_error", message="AVP source is unavailable"
            ) from error

        messages = self._prompt_builder.build(resume_data=job.resume_data, avp=avp)
        try:
            generated_content = await self._llm_client.generate(messages)
        except LlmTimeoutError as error:
            raise DocumentProcessingError(
                code="llm_timeout", message="LLM request timed out"
            ) from error
        except LlmInvalidResponseError as error:
            raise DocumentProcessingError(
                code="llm_invalid_response", message="Invalid LLM response"
            ) from error
        except LlmClientError as error:
            raise DocumentProcessingError(
                code="llm_api_error", message="LLM API request failed"
            ) from error

        if not isinstance(generated_content, str) or not generated_content.strip():
            raise DocumentProcessingError(
                code="invalid_generated_document",
                message="Generated document is empty",
            )
        generated_content = generated_content.strip()
        if FENCED_DOCUMENT.fullmatch(generated_content):
            raise DocumentProcessingError(
                code="invalid_generated_document",
                message="Generated document has an invalid format",
            )
        return GeneratedDocument(content=generated_content, format="asciidoc")
