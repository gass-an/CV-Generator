import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.exceptions import (
    DocumentGenerationFailedError,
    DocumentJobNotFoundError,
    DocumentJobNotReadyError,
)
from app.schemas.document import (
    CreateCvDocumentRequest,
    DocumentJobCreatedResponse,
    DocumentJobStatusResponse,
    DocumentResultResponse,
)
from app.services.document_job_service import (
    DocumentJobService,
    get_document_job_service,
)

router = APIRouter(prefix="/documents", tags=["documents"])

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
    request: CreateCvDocumentRequest,
    service: DocumentService,
) -> DocumentJobCreatedResponse:
    job = await service.create_cv_job(
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
