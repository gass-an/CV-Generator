import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.exceptions import (
    DocumentGenerationFailedError,
    DocumentJobNotFoundError,
    DocumentJobNotReadyError,
    DocumentResultUnavailableError,
)
from app.models.document_job import DocumentType
from app.renderers import DocxRenderer, DocxRenderingError
from app.schemas.document import (
    CreateDocumentRequest,
    DocumentJobCreatedResponse,
    DocumentJobStatusResponse,
    DocumentResultResponse,
)
from app.services.document_job_service import (
    DocumentJobService,
    get_document_job_service,
)

router = APIRouter(prefix="/documents", tags=["documents"])

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

DocumentService = Annotated[DocumentJobService, Depends(get_document_job_service)]


def not_found_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "document_job_not_found", "message": "Document job not found"},
    )


@router.post(
    "/cv",
    response_model=DocumentJobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_cv_document(
    request: CreateDocumentRequest,
    service: DocumentService,
) -> DocumentJobCreatedResponse:
    job = await service.create_job(
        document_type=DocumentType.CV,
        avp_number=request.avp_number,
        resume_data=request.resume,
    )
    return DocumentJobCreatedResponse(id=job.id, status=job.status)


@router.post(
    "/cover-letter",
    response_model=DocumentJobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_cover_letter_document(
    request: CreateDocumentRequest,
    service: DocumentService,
) -> DocumentJobCreatedResponse:
    job = await service.create_job(
        document_type=DocumentType.COVER_LETTER,
        avp_number=request.avp_number,
        resume_data=request.resume,
    )
    return DocumentJobCreatedResponse(id=job.id, status=job.status)


@router.get("/{job_id}/status", response_model=DocumentJobStatusResponse)
async def get_document_status(
    job_id: uuid.UUID,
    service: DocumentService,
) -> DocumentJobStatusResponse:
    try:
        job = await service.get_job(job_id)
    except DocumentJobNotFoundError as error:
        raise not_found_error() from error

    return DocumentJobStatusResponse(
        id=job.id,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.get("/{job_id}", response_model=DocumentResultResponse)
async def get_document_result(
    job_id: uuid.UUID,
    service: DocumentService,
) -> DocumentResultResponse:
    try:
        job = await service.get_result(job_id)
    except DocumentJobNotFoundError as error:
        raise not_found_error() from error
    except DocumentJobNotReadyError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_not_ready",
                "message": "Document generation is not complete",
            },
        ) from error
    except DocumentGenerationFailedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_generation_failed",
                "message": "Document generation failed",
            },
        ) from error

    return DocumentResultResponse(
        id=job.id,
        type=job.document_type,
        format=job.result_format,
        content=job.result_content,
    )


@router.get("/{job_id}/download")
async def download_document(
    job_id: uuid.UUID,
    service: DocumentService,
) -> Response:
    try:
        job = await service.get_asciidoc_job(job_id)
        content = DocxRenderer().render(job.result_content or "")
    except DocumentJobNotFoundError as error:
        raise not_found_error() from error
    except DocumentJobNotReadyError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_not_ready",
                "message": "Document generation is not complete",
            },
        ) from error
    except DocumentGenerationFailedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_generation_failed",
                "message": "Document generation failed",
            },
        ) from error
    except DocumentResultUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_result_unavailable",
                "message": "Document result is unavailable",
            },
        ) from error
    except DocxRenderingError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "document_rendering_failed",
                "message": "Document rendering failed",
            },
        ) from error

    filename_prefix = {
        DocumentType.CV: "cv",
        DocumentType.COVER_LETTER: "lettre-motivation",
    }[job.document_type]
    return Response(
        content=content,
        media_type=DOCX_MEDIA_TYPE,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename_prefix}-{job_id}.docx"'
            ),
        },
    )
