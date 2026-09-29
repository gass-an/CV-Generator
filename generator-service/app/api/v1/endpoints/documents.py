import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

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
    ErrorResponse,
)
from app.services.document_job_service import (
    DocumentJobService,
    get_document_job_service,
)

router = APIRouter(prefix="/documents", tags=["Documents"])

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

DocumentService = Annotated[DocumentJobService, Depends(get_document_job_service)]
DocumentId = Annotated[
    uuid.UUID,
    Path(alias="id", description="Identifiant unique du document."),
]

NOT_FOUND_RESPONSE = {
    "model": ErrorResponse,
    "description": "Aucun document ne correspond à cet identifiant.",
}
CONFLICT_RESPONSE = {
    "model": ErrorResponse,
    "description": (
        "Le document n'est pas encore prêt, sa génération a échoué ou son "
        "résultat n'est pas exploitable."
    ),
}


def not_found_error() -> HTTPException:
    """Construit la réponse métier commune lorsqu'un job est introuvable."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "document_job_not_found",
            "message": "Le document est introuvable",
        },
    )


@router.post(
    "/cv",
    response_model=DocumentJobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Créer une génération de CV",
    description=(
        "Démarre la génération asynchrone d'un CV à partir d'un JSON Resume "
        "et d'un numéro d'AVP exact."
    ),
    response_description=(
        "Génération démarrée avec un identifiant de document et le statut `pending`."
    ),
    responses={
        422: {"description": "Le payload JSON est invalide."},
    },
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
    summary="Créer une génération de lettre de motivation",
    description=(
        "Démarre la génération asynchrone d'une lettre de motivation à partir "
        "d'un JSON Resume et d'un numéro d'AVP exact."
    ),
    response_description=(
        "Génération démarrée avec un identifiant de document et le statut `pending`."
    ),
    responses={
        422: {"description": "Le payload JSON est invalide."},
    },
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


@router.get(
    "/{id}/status",
    response_model=DocumentJobStatusResponse,
    summary="Consulter le statut d'un document",
    description=(
        "Retourne l'état courant du traitement et ses horodatages sans exposer "
        "le JSON Resume du candidat."
    ),
    response_description="État courant de la génération du document.",
    responses={404: NOT_FOUND_RESPONSE, 422: {"description": "Identifiant invalide."}},
)
async def get_document_status(
    document_id: DocumentId,
    service: DocumentService,
) -> DocumentJobStatusResponse:
    try:
        job = await service.get_job(document_id)
    except DocumentJobNotFoundError as error:
        raise not_found_error() from error

    return DocumentJobStatusResponse(
        id=job.id,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.get(
    "/{id}",
    response_model=DocumentResultResponse,
    summary="Récupérer le document généré",
    description=(
        "Retourne le contenu source AsciiDoc d'un document dont la génération "
        "est terminée. Une réponse 409 est renvoyée tant que le traitement n'est "
        "pas terminé ou s'il a échoué."
    ),
    response_description="Document généré au format AsciiDoc.",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: {"description": "Identifiant invalide."},
    },
)
async def get_document_result(
    document_id: DocumentId,
    service: DocumentService,
) -> DocumentResultResponse:
    try:
        job = await service.get_result(document_id)
    except DocumentJobNotFoundError as error:
        raise not_found_error() from error
    except DocumentJobNotReadyError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_not_ready",
                "message": "La génération du document n'est pas terminée",
            },
        ) from error
    except DocumentGenerationFailedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_generation_failed",
                "message": "La génération du document a échoué",
            },
        ) from error

    return DocumentResultResponse(
        id=job.id,
        type=job.document_type,
        format=job.result_format,
        content=job.result_content,
    )


@router.get(
    "/{id}/download",
    summary="Télécharger le document généré",
    description=(
        "Télécharge un document terminé au format DOCX. Le résultat source est "
        "stocké en AsciiDoc et le fichier DOCX est généré à la demande."
    ),
    response_description="Fichier DOCX généré à la demande.",
    responses={
        200: {
            "content": {DOCX_MEDIA_TYPE: {}},
            "description": "Document généré au format DOCX.",
        },
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: {"description": "Identifiant invalide."},
        500: {
            "model": ErrorResponse,
            "description": "Le rendu du fichier DOCX a échoué.",
        },
    },
)
async def download_document(
    document_id: DocumentId,
    service: DocumentService,
) -> Response:
    try:
        job = await service.get_asciidoc_job(document_id)
        content = DocxRenderer().render(job.result_content or "")
    except DocumentJobNotFoundError as error:
        raise not_found_error() from error
    except DocumentJobNotReadyError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_not_ready",
                "message": "La génération du document n'est pas terminée",
            },
        ) from error
    except DocumentGenerationFailedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_generation_failed",
                "message": "La génération du document a échoué",
            },
        ) from error
    except DocumentResultUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_result_unavailable",
                "message": "Le résultat du document est indisponible",
            },
        ) from error
    except DocxRenderingError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "document_rendering_failed",
                "message": "La génération du fichier DOCX a échoué",
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
                f'attachment; filename="{filename_prefix}-{document_id}.docx"'
            ),
        },
    )
