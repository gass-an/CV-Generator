import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import quote, urlencode, urlsplit
from zoneinfo import ZoneInfo

from cv_generator_shared.dto import ApiKeyWithClientData
from cv_generator_shared.exceptions import (
    ApiClientInactiveError,
    ApiClientNotFoundError,
    ApiKeyNotFoundError,
)
from cv_generator_shared.services import ApiKeyService
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.activity import ActivityFilters, ActivityJob, AdminActivityService
from app.admin_security import (
    AdminPrincipal,
    AdminSecurityService,
    IssuedAdminSession,
    LoginFailure,
)
from app.config import get_settings
from app.database import get_business_session, get_security_session
from app.llm_router import LlmRouterClient, LlmRouterError
from app.llm_service import (
    AdminLlmService,
    LlmModelConflictError,
    LlmModelNotFoundError,
    LlmModelSnapshot,
)

ROOT = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=ROOT / "templates")


def admin_datetime(value: datetime | None) -> str:
    """Affiche un instant dans le fuseau configuré pour l'administration."""
    if value is None:
        return ""
    aware_value = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    return aware_value.astimezone(get_settings().timezone).strftime("%d/%m/%Y %H:%M")


templates.env.filters["admin_datetime"] = admin_datetime

SecuritySession = Annotated[AsyncSession, Depends(get_security_session)]
BusinessSession = Annotated[AsyncSession, Depends(get_business_session)]


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.validate_security()
    application.state.llm_router = LlmRouterClient(
        base_url=settings.llm_base_url,
        timeout=settings.llm_management_timeout_seconds,
        activation_timeout=settings.llm_activation_timeout_seconds,
    )
    try:
        yield
    finally:
        await application.state.llm_router.aclose()


app = FastAPI(
    title="Administration privée de CV-Generator",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.middleware("http")
async def security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; "
        "img-src 'self'; form-action 'self'; frame-ancestors 'none'"
    )
    return response


def security_service(session: SecuritySession) -> AdminSecurityService:
    return AdminSecurityService(session, get_settings())


SecurityService = Annotated[AdminSecurityService, Depends(security_service)]


def _set_session_cookies(response: Response, issued: IssuedAdminSession) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.admin_session_cookie_name,
        issued.token,
        httponly=True,
        secure=settings.admin_cookie_secure,
        samesite="strict",
        max_age=settings.admin_session_ttl_seconds,
    )
    response.set_cookie(
        settings.admin_csrf_cookie_name,
        issued.csrf_token,
        httponly=False,
        secure=settings.admin_cookie_secure,
        samesite="strict",
        max_age=settings.admin_session_ttl_seconds,
    )


def _clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.admin_session_cookie_name)
    response.delete_cookie(settings.admin_csrf_cookie_name)


def _client_ip(request: Request) -> str:
    settings = get_settings()
    peer = request.client.host if request.client is not None else "unknown"
    if peer in settings.trusted_proxy_ips:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()[:45]
    return peer[:45]


def _valid_origin(request: Request) -> bool:
    origin = request.headers.get("Origin")
    fetch_site = request.headers.get("Sec-Fetch-Site")
    expected_origin = get_settings().admin_base_url.rstrip("/")

    # Une requête déclarée comme provenant d'un autre site est rejetée.
    if fetch_site is not None and fetch_site != "same-origin":
        return False

    # Certains navigateurs avec protections renforcées envoient Origin: null.
    # On ne l'accepte que si Sec-Fetch-Site confirme la même origine.
    if origin == "null":
        return fetch_site == "same-origin"

    # Conserver la compatibilité avec les clients qui n'envoient pas Origin.
    if origin is None:
        return True

    return origin.rstrip("/") == expected_origin


async def current_admin(
    request: Request,
    service: SecurityService,
) -> AdminPrincipal:
    settings = get_settings()
    principal = await service.authenticate(
        request.cookies.get(settings.admin_session_cookie_name),
        request.cookies.get(settings.admin_csrf_cookie_name),
    )
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return principal


CurrentAdmin = Annotated[AdminPrincipal, Depends(current_admin)]


class AdminLoginRequired(Exception):
    """Signale qu'une navigation HTML exige une nouvelle connexion."""


async def current_admin_page(
    request: Request,
    service: SecurityService,
) -> AdminPrincipal:
    settings = get_settings()
    principal = await service.authenticate(
        request.cookies.get(settings.admin_session_cookie_name),
        request.cookies.get(settings.admin_csrf_cookie_name),
    )
    if principal is None:
        raise AdminLoginRequired
    return principal


PageAdmin = Annotated[AdminPrincipal, Depends(current_admin_page)]

DOCUMENT_TYPE_LABELS = {
    "cv": "CV",
    "cover_letter": "Lettre de motivation",
    "interview_prep": "Guide d’entretien",
}
JOB_STATUS_LABELS = {
    "pending": "En attente",
    "processing": "En cours",
    "completed": "Terminée",
    "failed": "Échouée",
    "cancelled": "Annulée",
}

LLM_STATUS_LABELS = {
    "unloaded": "Disponible",
    "loaded": "Chargé",
    "loading": "Chargement en cours",
    "downloading": "Téléchargement en cours",
    "incomplete": "Incomplet",
    "sleeping": "En veille",
    "error": "Erreur",
}


def _llm_router(request: Request) -> LlmRouterClient:
    router = getattr(request.app.state, "llm_router", None)
    if router is None:
        settings = get_settings()
        router = LlmRouterClient(
            base_url=settings.llm_base_url,
            timeout=settings.llm_management_timeout_seconds,
            activation_timeout=settings.llm_activation_timeout_seconds,
        )
        request.app.state.llm_router = router
    return router


def _require_llm_management() -> None:
    settings = get_settings()
    if not settings.llm_management_enabled or not settings.llm_base_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La gestion des modèles LLM est désactivée.",
        )


def _llm_model_json(
    model: object, selected: str, loaded: str | None
) -> dict[str, object]:
    from app.llm_router import RouterModel

    assert isinstance(model, RouterModel)
    percentage = None
    if model.progress_done is not None and model.progress_total:
        percentage = round(model.progress_done * 100 / model.progress_total, 1)
    effective_status = "error" if model.failed else model.status
    return {
        "id": model.id,
        "quantization": model.quantization,
        "status": effective_status,
        "status_label": LLM_STATUS_LABELS.get(effective_status, effective_status),
        "size": model.size,
        "progress_done": model.progress_done,
        "progress_total": model.progress_total,
        "progress_percentage": percentage,
        "selected": model.id == selected,
        "loaded": model.id == loaded,
    }


@app.get("/llm-models", response_class=HTMLResponse)
async def llm_models_page(
    request: Request,
    principal: PageAdmin,
    session: BusinessSession,
    message: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    settings = get_settings()
    snapshot = None
    router_error = None
    if settings.llm_management_enabled and settings.llm_base_url:
        service = AdminLlmService(
            session, _llm_router(request), fallback_model=settings.llm_model
        )
        try:
            snapshot = await service.snapshot()
        except LlmRouterError as exc:
            router_error = str(exc)
            snapshot = LlmModelSnapshot(
                models=[],
                selected_model=await service.selected_model(),
                loaded_model=None,
            )
    return templates.TemplateResponse(
        request=request,
        name="llm_models.html",
        context={
            "principal": principal,
            "csrf_token": principal.csrf_token,
            "snapshot": snapshot,
            "management_enabled": settings.llm_management_enabled,
            "router_error": router_error,
            "message": message,
            "error": error,
            "status_labels": LLM_STATUS_LABELS,
        },
    )


@app.get("/llm-models/data")
async def llm_models_data(
    request: Request, principal: CurrentAdmin, session: BusinessSession
) -> dict[str, object]:
    del principal
    _require_llm_management()
    settings = get_settings()
    try:
        snapshot = await AdminLlmService(
            session, _llm_router(request), fallback_model=settings.llm_model
        ).snapshot()
    except LlmRouterError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {
        "selected_model": snapshot.selected_model,
        "loaded_model": snapshot.loaded_model,
        "models": [
            _llm_model_json(model, snapshot.selected_model, snapshot.loaded_model)
            for model in snapshot.models
        ],
    }


async def _llm_action(
    action: str,
    model: str,
    request: Request,
    principal: AdminPrincipal,
    session: AsyncSession,
    csrf_token: str,
) -> RedirectResponse:
    _verify_csrf(request, principal, csrf_token)
    _require_llm_management()
    settings = get_settings()
    service = AdminLlmService(
        session, _llm_router(request), fallback_model=settings.llm_model
    )
    try:
        if action == "download":
            normalized = await service.download(model)
            success = f"Téléchargement lancé pour {normalized}."
        elif action == "activate":
            await service.activate(model)
            success = f"Le modèle {model.strip()} est sélectionné et chargé."
        else:
            await service.unload(model)
            success = f"Le modèle {model.strip()} a été déchargé."
    except ValueError as exc:
        code, detail = 422, str(exc)
    except LlmModelNotFoundError as exc:
        code, detail = 404, str(exc)
    except LlmModelConflictError as exc:
        code, detail = 409, str(exc)
    except LlmRouterError as exc:
        code, detail = 503, str(exc)
    else:
        return RedirectResponse(
            f"/llm-models?message={quote(success, safe='')}", status_code=303
        )
    return RedirectResponse(
        f"/llm-models?error={quote(detail, safe='')}&code={code}", status_code=303
    )


@app.post("/llm-models/download")
async def download_llm_model(
    request: Request,
    principal: PageAdmin,
    session: BusinessSession,
    model: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
) -> RedirectResponse:
    return await _llm_action("download", model, request, principal, session, csrf_token)


@app.post("/llm-models/activate")
async def activate_llm_model(
    request: Request,
    principal: PageAdmin,
    session: BusinessSession,
    model: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
) -> RedirectResponse:
    return await _llm_action("activate", model, request, principal, session, csrf_token)


@app.post("/llm-models/unload")
async def unload_llm_model(
    request: Request,
    principal: PageAdmin,
    session: BusinessSession,
    model: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
) -> RedirectResponse:
    return await _llm_action("unload", model, request, principal, session, csrf_token)


def _safe_next_path(value: str | None) -> str:
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/"
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return "/"
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or "\\" in value:
        return "/"
    return value


@app.exception_handler(AdminLoginRequired)
async def admin_login_required_handler(
    request: Request, error: AdminLoginRequired
) -> RedirectResponse:
    del error
    settings = get_settings()
    had_session = bool(request.cookies.get(settings.admin_session_cookie_name))
    destination = request.url.path if request.method == "GET" else "/"
    if request.method == "GET" and request.url.query:
        destination = f"{destination}?{request.url.query}"
    location = f"/login?next={quote(_safe_next_path(destination), safe='')}"
    if had_session:
        location += "&expired=1"
    response = RedirectResponse(location, status_code=status.HTTP_303_SEE_OTHER)
    _clear_session_cookies(response)
    return response


def _verify_csrf(request: Request, principal: AdminPrincipal, csrf_token: str) -> None:
    if not _valid_origin(request) or not secrets_compare(
        principal.csrf_token, csrf_token
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


def secrets_compare(first: str, second: str) -> bool:
    import hmac

    return hmac.compare_digest(first, second)


@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    service: SecurityService,
    next: str = "/",
    expired: bool = False,
) -> Response:
    settings = get_settings()
    destination = _safe_next_path(next)
    principal = await service.authenticate(
        request.cookies.get(settings.admin_session_cookie_name),
        request.cookies.get(settings.admin_csrf_cookie_name),
    )
    if principal is not None:
        return RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)
    issued = await service.issue_anonymous_session()
    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "csrf_token": issued.csrf_token,
            "csrf_expires_at": issued.expires_at.isoformat(),
            "error": None,
            "next": destination,
            "session_expired": expired,
        },
    )
    _set_session_cookies(response, issued)
    return response


@app.get("/login/csrf")
async def renew_login_csrf(request: Request, service: SecurityService) -> Response:
    """Remplace ponctuellement la session anonyme d'un formulaire de connexion."""
    if not _valid_origin(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    settings = get_settings()
    principal = await service.authenticate(
        request.cookies.get(settings.admin_session_cookie_name),
        request.cookies.get(settings.admin_csrf_cookie_name),
    )
    if principal is not None:
        return JSONResponse(
            {"authenticated": True}, status_code=status.HTTP_409_CONFLICT
        )
    issued = await service.issue_anonymous_session()
    response = JSONResponse(
        {
            "csrf_token": issued.csrf_token,
            "expires_at": issued.expires_at.isoformat(),
        }
    )
    _set_session_cookies(response, issued)
    return response


@app.post("/login")
async def login(
    request: Request,
    service: SecurityService,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/",
) -> HTMLResponse:
    settings = get_settings()
    destination = _safe_next_path(next)
    if not _valid_origin(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    issued = await service.login(
        current_token=request.cookies.get(settings.admin_session_cookie_name),
        csrf_token=csrf_token,
        username=username,
        password=password,
        ip_address=_client_ip(request),
    )
    if issued is LoginFailure.INVALID_CSRF:
        replacement = await service.issue_anonymous_session()
        response = templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": replacement.csrf_token,
                "csrf_expires_at": replacement.expires_at.isoformat(),
                "error": (
                    "La session du formulaire a expiré. Vos identifiants n’ont pas "
                    "été vérifiés ; veuillez réessayer."
                ),
                "next": destination,
                "session_expired": False,
                "username": username,
            },
            status_code=status.HTTP_403_FORBIDDEN,
        )
        _set_session_cookies(response, replacement)
        return response
    if issued is LoginFailure.INVALID_CREDENTIALS:
        replacement = await service.issue_anonymous_session()
        response = templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": replacement.csrf_token,
                "csrf_expires_at": replacement.expires_at.isoformat(),
                "error": "Identifiants invalides ou connexion temporairement bloquée.",
                "next": destination,
                "session_expired": False,
                "username": username,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        _set_session_cookies(response, replacement)
        return response
    response = RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)
    _set_session_cookies(response, issued)
    return response


@app.post("/logout")
async def logout(
    request: Request,
    service: SecurityService,
    principal: PageAdmin,
    csrf_token: Annotated[str, Form()],
) -> RedirectResponse:
    _verify_csrf(request, principal, csrf_token)
    settings = get_settings()
    await service.logout(
        request.cookies.get(settings.admin_session_cookie_name), csrf_token
    )
    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    _clear_session_cookies(response)
    return response


def _key_status(item: ApiKeyWithClientData, now: datetime) -> str:
    if item.key.revoked_at is not None:
        return "Révoquée"
    if not item.client_is_active:
        return "Propriétaire désactivé"
    if item.key.expires_at is not None and item.key.expires_at <= now:
        return "Expirée"
    return "Active"


def _activity_filters(
    *,
    client_id: uuid.UUID | None,
    document_type: str | None,
    job_status: str | None,
    avp_number: str | None,
    created_from: date | None,
    created_to: date | None,
    page: int,
) -> ActivityFilters:
    from cv_generator_shared.document_jobs import DocumentJobStatus, DocumentType

    return ActivityFilters(
        client_id=client_id,
        document_type=DocumentType(document_type) if document_type else None,
        status=DocumentJobStatus(job_status) if job_status else None,
        avp_number=avp_number.strip() if avp_number and avp_number.strip() else None,
        created_from=created_from,
        created_to=created_to,
        page=max(page, 1),
    )


def _activity_query(filters: ActivityFilters, page: int) -> str:
    values = {
        "client_id": str(filters.client_id) if filters.client_id else None,
        "document_type": filters.document_type.value if filters.document_type else None,
        "status": filters.status.value if filters.status else None,
        "avp_number": filters.avp_number,
        "created_from": filters.created_from.isoformat()
        if filters.created_from
        else None,
        "created_to": filters.created_to.isoformat() if filters.created_to else None,
        "page": page,
    }
    return urlencode({key: value for key, value in values.items() if value is not None})


def _activity_job_json(job: ActivityJob) -> dict[str, object]:
    return {
        "id": str(job.id),
        "client_id": str(job.client_id) if job.client_id else None,
        "owner_name": job.owner_name,
        "owner_active": job.owner_active,
        "document_type": job.document_type.value,
        "document_type_label": DOCUMENT_TYPE_LABELS[job.document_type.value],
        "status": job.status.value,
        "status_label": JOB_STATUS_LABELS[job.status.value],
        "avp_number": job.avp_number,
        "candidate_name": job.candidate_name,
        "created_at": admin_datetime(job.created_at),
        "started_at": admin_datetime(job.started_at),
        "completed_at": admin_datetime(job.completed_at),
        "cancelled_at": admin_datetime(job.cancelled_at),
        "llm_model": job.llm_model,
        "duration_seconds": job.duration_seconds,
    }


@app.get("/activity", response_class=HTMLResponse)
async def activity_page(
    request: Request,
    principal: PageAdmin,
    session: BusinessSession,
    client_id: uuid.UUID | None = None,
    document_type: str | None = None,
    job_status: Annotated[str | None, Query(alias="status")] = None,
    avp_number: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    page: int = 1,
) -> HTMLResponse:
    try:
        filters = _activity_filters(
            client_id=client_id,
            document_type=document_type,
            job_status=job_status,
            avp_number=avp_number,
            created_from=created_from,
            created_to=created_to,
            page=page,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
        ) from error
    service = AdminActivityService(session, get_settings().timezone)
    snapshot = await service.snapshot(filters)
    return templates.TemplateResponse(
        request=request,
        name="activity.html",
        context={
            "principal": principal,
            "csrf_token": principal.csrf_token,
            "snapshot": snapshot,
            "filters": filters,
            "clients": await service.list_clients(),
            "document_type_labels": DOCUMENT_TYPE_LABELS,
            "job_status_labels": JOB_STATUS_LABELS,
            "previous_query": _activity_query(filters, snapshot.page - 1),
            "next_query": _activity_query(filters, snapshot.page + 1),
        },
    )


@app.get("/activity/data")
async def activity_data(
    principal: CurrentAdmin,
    session: BusinessSession,
    client_id: uuid.UUID | None = None,
    document_type: str | None = None,
    job_status: Annotated[str | None, Query(alias="status")] = None,
    avp_number: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    page: int = 1,
) -> dict[str, object]:
    del principal
    try:
        filters = _activity_filters(
            client_id=client_id,
            document_type=document_type,
            job_status=job_status,
            avp_number=avp_number,
            created_from=created_from,
            created_to=created_to,
            page=page,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
        ) from error
    snapshot = await AdminActivityService(session, get_settings().timezone).snapshot(
        filters
    )
    return {
        "counters": {
            "pending": snapshot.counters.pending,
            "processing": snapshot.counters.processing,
            "completed_today": snapshot.counters.completed_today,
            "failed_today": snapshot.counters.failed_today,
        },
        "recent": [_activity_job_json(job) for job in snapshot.recent],
        "history": [_activity_job_json(job) for job in snapshot.history],
        "pagination": {
            "page": snapshot.page,
            "page_count": snapshot.page_count,
            "page_size": snapshot.page_size,
            "total": snapshot.total,
        },
        "refreshed_at": admin_datetime(snapshot.refreshed_at),
    }


@app.get("/", response_class=HTMLResponse)
async def key_table(
    request: Request,
    principal: PageAdmin,
    session: BusinessSession,
    status_filter: str = "all",
    page: int = 1,
) -> HTMLResponse:
    page = max(page, 1)
    page_size = 50
    keys = await ApiKeyService(session).list_all_keys(
        offset=(page - 1) * page_size,
        limit=page_size + 1,
        active_only=status_filter == "active",
    )
    has_next = len(keys) > page_size
    keys = keys[:page_size]
    now = datetime.now(UTC)
    rows = [{"item": item, "status": _key_status(item, now)} for item in keys]
    return templates.TemplateResponse(
        request=request,
        name="keys.html",
        context={
            "principal": principal,
            "csrf_token": principal.csrf_token,
            "rows": rows,
            "status_filter": status_filter,
            "page": page,
            "has_next": has_next,
        },
    )


@app.get("/keys/new", response_class=HTMLResponse)
async def new_key_form(
    request: Request,
    principal: PageAdmin,
    security: SecurityService,
    session: BusinessSession,
) -> HTMLResponse:
    clients = await ApiKeyService(session).list_clients()
    form_token = await security.issue_form_token(principal)
    return templates.TemplateResponse(
        request=request,
        name="new_key.html",
        context={
            "principal": principal,
            "csrf_token": principal.csrf_token,
            "form_token": form_token,
            "clients": clients,
            "timezone_label": get_settings().timezone_label,
            "error": None,
        },
    )


def _parse_expiration(
    value: str, *, timezone: ZoneInfo | None = None
) -> datetime | None:
    if not value.strip():
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone or get_settings().timezone)
    return parsed.astimezone(UTC)


@app.post("/keys", response_class=HTMLResponse)
async def create_key(
    request: Request,
    principal: PageAdmin,
    security: SecurityService,
    session: BusinessSession,
    csrf_token: Annotated[str, Form()],
    form_token: Annotated[str, Form()],
    client_id: Annotated[str, Form()] = "",
    new_client_name: Annotated[str, Form()] = "",
    key_name: Annotated[str, Form()] = "",
    expires_at: Annotated[str, Form()] = "",
    confirm_duplicate: Annotated[str, Form()] = "",
) -> HTMLResponse:
    _verify_csrf(request, principal, csrf_token)
    if not await security.consume_form_token(principal, form_token):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT)
    service = ApiKeyService(session)
    try:
        expiration = _parse_expiration(expires_at)
        if client_id:
            client = await service.get_client(uuid.UUID(client_id))
            created = await service.create_key(
                client.id, name=key_name or None, expires_at=expiration
            )
        else:
            existing = await service.list_clients()
            duplicates = [
                item for item in existing if item.name == new_client_name.strip()
            ]
            if duplicates and confirm_duplicate != "yes":
                raise ValueError(
                    "Un propriétaire porte déjà ce nom. Confirmez la création "
                    "d'une personne distincte."
                )
            result = await service.create_client_with_key(
                client_name=new_client_name,
                key_name=key_name or None,
                expires_at=expiration,
            )
            client = result.client
            created = result.created_key
    except (ValueError, ApiClientInactiveError, ApiClientNotFoundError) as error:
        clients = await ApiKeyService(session).list_clients()
        replacement_token = await security.issue_form_token(principal)
        return templates.TemplateResponse(
            request=request,
            name="new_key.html",
            context={
                "principal": principal,
                "csrf_token": principal.csrf_token,
                "form_token": replacement_token,
                "clients": clients,
                "timezone_label": get_settings().timezone_label,
                "error": str(error),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return templates.TemplateResponse(
        request=request,
        name="created_key.html",
        context={
            "principal": principal,
            "csrf_token": principal.csrf_token,
            "client": client,
            "created": created,
        },
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@app.post("/keys/{key_id}/revoke")
async def revoke_key(
    key_id: uuid.UUID,
    request: Request,
    principal: PageAdmin,
    session: BusinessSession,
    csrf_token: Annotated[str, Form()],
) -> RedirectResponse:
    _verify_csrf(request, principal, csrf_token)
    try:
        await ApiKeyService(session).revoke_key(key_id)
    except ApiKeyNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/clients", response_class=HTMLResponse)
async def client_table(
    request: Request,
    principal: PageAdmin,
    session: BusinessSession,
) -> HTMLResponse:
    clients = await ApiKeyService(session).list_clients()
    return templates.TemplateResponse(
        request=request,
        name="clients.html",
        context={
            "principal": principal,
            "csrf_token": principal.csrf_token,
            "clients": clients,
        },
    )


@app.post("/clients/{client_id}/disable")
async def disable_client(
    client_id: uuid.UUID,
    request: Request,
    principal: PageAdmin,
    session: BusinessSession,
    csrf_token: Annotated[str, Form()],
) -> RedirectResponse:
    _verify_csrf(request, principal, csrf_token)
    try:
        await ApiKeyService(session).disable_client(client_id)
    except ApiClientNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return RedirectResponse("/clients", status_code=status.HTTP_303_SEE_OTHER)
