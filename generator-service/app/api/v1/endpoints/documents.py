import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from app.api.dependencies import AuthenticatedIdentity
from app.core.exceptions import (
    DocumentGenerationFailedError,
    DocumentJobNotFoundError,
    DocumentJobNotReadyError,
    DocumentResultUnavailableError,
)
from app.models.document_job import DocumentJob, DocumentJobStatus, DocumentType
from app.renderers import (
    DocxRenderer,
    DocxRenderingError,
    MarkdownRenderer,
    MarkdownRenderingError,
)
from app.schemas.document import (
    CreateDocumentRequest,
    DocumentAvpNumbersResponse,
    DocumentHistoryItemResponse,
    DocumentHistoryResponse,
    DocumentJobCreatedResponse,
    DocumentJobStatusResponse,
    DocumentResultResponse,
    ErrorResponse,
)
from app.services.document_job_service import (
    DocumentJobService,
    get_document_job_service,
)
from app.services.pdf_conversion_service import (
    PdfConversionError,
    PdfConversionTimeoutError,
    PdfConverter,
)

router = APIRouter(prefix="/documents", tags=["Documents"])

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
PDF_MEDIA_TYPE = "application/pdf"
ASCIIDOC_MEDIA_TYPE = "text/asciidoc; charset=utf-8"
MARKDOWN_MEDIA_TYPE = "text/markdown; charset=utf-8"
CACHE_CONTROL_HEADERS = {"Cache-Control": "private, no-store"}

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


def document_filename_prefix(document_type: DocumentType) -> str:
    return {
        DocumentType.CV: "cv",
        DocumentType.COVER_LETTER: "lettre-motivation",
        DocumentType.INTERVIEW_PREP: "guide-entretien",
    }[document_type]


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
    identity: AuthenticatedIdentity,
) -> DocumentJobCreatedResponse:
    job = await service.create_job(
        client_id=identity.client_id,
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
    identity: AuthenticatedIdentity,
) -> DocumentJobCreatedResponse:
    job = await service.create_job(
        client_id=identity.client_id,
        document_type=DocumentType.COVER_LETTER,
        avp_number=request.avp_number,
        resume_data=request.resume,
    )
    return DocumentJobCreatedResponse(id=job.id, status=job.status)


@router.post(
    "/interview-prep",
    response_model=DocumentJobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Créer un guide de préparation à l'entretien",
    description=(
        "Démarre la génération asynchrone d'un guide de préparation à "
        "l'entretien à partir d'un JSON Resume et d'un numéro d'AVP exact."
    ),
    response_description=(
        "Génération démarrée avec un identifiant de document et le statut `pending`."
    ),
    responses={422: {"description": "Le payload JSON est invalide."}},
)
async def create_interview_prep_document(
    request: CreateDocumentRequest,
    service: DocumentService,
    identity: AuthenticatedIdentity,
) -> DocumentJobCreatedResponse:
    job = await service.create_job(
        client_id=identity.client_id,
        document_type=DocumentType.INTERVIEW_PREP,
        avp_number=request.avp_number,
        resume_data=request.resume,
    )
    return DocumentJobCreatedResponse(id=job.id, status=job.status)


@router.get(
    "",
    response_model=DocumentHistoryResponse,
    summary="Consulter l'historique des documents",
    description=(
        "Retourne une page des générations appartenant au client authentifié, "
        "sans exposer le JSON Resume ni le contenu des documents."
    ),
    response_description="Page de l'historique triée du plus récent au plus ancien.",
    responses={422: {"description": "Paramètres de pagination ou filtres invalides."}},
)
async def list_document_history(
    service: DocumentService,
    identity: AuthenticatedIdentity,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    document_type: DocumentType | None = None,
    status_filter: Annotated[
        DocumentJobStatus | None,
        Query(alias="status"),
    ] = None,
    avp_number: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
) -> DocumentHistoryResponse:
    items, total = await service.list_history(
        client_id=identity.client_id,
        limit=limit,
        offset=offset,
        document_type=document_type,
        status=status_filter,
        avp_number=avp_number.strip() if avp_number else None,
    )
    return DocumentHistoryResponse(
        items=[
            DocumentHistoryItemResponse(
                id=item.id,
                type=item.document_type,
                status=item.status,
                avp_number=item.avp_number,
                candidate_name=item.candidate_name,
                created_at=item.created_at,
                started_at=item.started_at,
                completed_at=item.completed_at,
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/avp-numbers",
    response_model=DocumentAvpNumbersResponse,
    summary="Lister les numéros AVP de l'historique",
    description=(
        "Retourne les numéros AVP distincts appartenant au client authentifié, "
        "triés alphabétiquement. Un préfixe insensible à la casse peut être fourni."
    ),
)
async def list_document_avp_numbers(
    service: DocumentService,
    identity: AuthenticatedIdentity,
    prefix: Annotated[str | None, Query(max_length=128)] = None,
) -> DocumentAvpNumbersResponse:
    items = await service.list_avp_numbers(
        client_id=identity.client_id,
        prefix=prefix,
    )
    return DocumentAvpNumbersResponse(items=items)


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
    identity: AuthenticatedIdentity,
) -> DocumentJobStatusResponse:
    try:
        job = await service.get_job(document_id, client_id=identity.client_id)
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
    identity: AuthenticatedIdentity,
) -> DocumentResultResponse:
    try:
        job = await service.get_result(document_id, client_id=identity.client_id)
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
    "/{id}/docx",
    summary="Télécharger le document en DOCX",
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
async def download_document_docx(
    document_id: DocumentId,
    service: DocumentService,
    identity: AuthenticatedIdentity,
) -> Response:
    job = await _get_export_job(document_id, service, identity)
    try:
        content = DocxRenderer().render(job.result_content or "")
    except DocxRenderingError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "document_rendering_failed",
                "message": "La génération du fichier DOCX a échoué",
            },
        ) from error

    filename_prefix = document_filename_prefix(job.document_type)
    return Response(
        content=content,
        media_type=DOCX_MEDIA_TYPE,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename_prefix}-{document_id}.docx"'
            ),
            **CACHE_CONTROL_HEADERS,
        },
    )


@router.get(
    "/{id}/pdf",
    summary="Prévisualiser le document en PDF",
    description=(
        "Génère à la demande le DOCX d'un document terminé, puis le convertit "
        "en PDF pour une prévisualisation authentifiée."
    ),
    response_description="Document PDF généré à la demande.",
    responses={
        200: {
            "content": {PDF_MEDIA_TYPE: {}},
            "description": "Document généré au format PDF.",
        },
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: {"description": "Identifiant invalide."},
        500: {
            "model": ErrorResponse,
            "description": "Le rendu ou la conversion PDF a échoué.",
        },
    },
)
async def preview_document_pdf(
    document_id: DocumentId,
    service: DocumentService,
    identity: AuthenticatedIdentity,
    converter: PdfConverter,
) -> Response:
    job = await _get_export_job(document_id, service, identity)
    try:
        docx_content = DocxRenderer().render(job.result_content or "")
        pdf_content = await converter.convert(docx_content)
    except DocxRenderingError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "document_rendering_failed",
                "message": "La génération du fichier DOCX a échoué",
            },
        ) from error
    except PdfConversionTimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "pdf_conversion_timeout",
                "message": "La conversion du document en PDF a expiré",
            },
        ) from error
    except PdfConversionError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "pdf_conversion_failed",
                "message": "La conversion du document en PDF a échoué",
            },
        ) from error

    filename_prefix = document_filename_prefix(job.document_type)
    return Response(
        content=pdf_content,
        media_type=PDF_MEDIA_TYPE,
        headers={
            "Content-Disposition": (
                f'inline; filename="{filename_prefix}-{document_id}.pdf"'
            ),
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "/{id}/adoc",
    summary="Télécharger le document source en AsciiDoc",
    description=(
        "Télécharge en UTF-8 le contenu AsciiDoc final stocké pour un document "
        "terminé, sans nouvelle génération ni conversion."
    ),
    response_description="Fichier source AsciiDoc stocké.",
    responses={
        200: {"content": {"text/asciidoc": {}}, "description": "Source AsciiDoc."},
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: {"description": "Identifiant invalide."},
    },
)
async def download_document_adoc(
    document_id: DocumentId,
    service: DocumentService,
    identity: AuthenticatedIdentity,
) -> Response:
    job = await _get_export_job(document_id, service, identity)
    filename = f"{document_filename_prefix(job.document_type)}-{document_id}.adoc"
    return Response(
        content=job.result_content or "",
        media_type=ASCIIDOC_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            **CACHE_CONTROL_HEADERS,
        },
    )


@router.get(
    "/{id}/md",
    summary="Télécharger le document en Markdown",
    description=(
        "Convertit à la demande en Markdown le contenu AsciiDoc final stocké, "
        "sans appel au LLM ni création d'un nouveau traitement."
    ),
    response_description="Fichier Markdown converti à la demande.",
    responses={
        200: {"content": {"text/markdown": {}}, "description": "Document Markdown."},
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: {"description": "Identifiant invalide."},
        500: {
            "model": ErrorResponse,
            "description": "La conversion Markdown a échoué.",
        },
    },
)
async def download_document_markdown(
    document_id: DocumentId,
    service: DocumentService,
    identity: AuthenticatedIdentity,
) -> Response:
    job = await _get_export_job(document_id, service, identity)
    try:
        content = MarkdownRenderer().render(job.result_content or "")
    except MarkdownRenderingError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "markdown_conversion_failed",
                "message": "La conversion du document en Markdown a échoué",
            },
        ) from error
    filename = f"{document_filename_prefix(job.document_type)}-{document_id}.md"
    return Response(
        content=content,
        media_type=MARKDOWN_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            **CACHE_CONTROL_HEADERS,
        },
    )


async def _get_export_job(
    document_id: uuid.UUID,
    service: DocumentJobService,
    identity: AuthenticatedIdentity,
) -> DocumentJob:
    try:
        return await service.get_asciidoc_job(document_id, client_id=identity.client_id)
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
