import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from cv_generator_shared.dto import ApiKeyWithClientData
from cv_generator_shared.exceptions import (
    ApiClientInactiveError,
    ApiClientNotFoundError,
    ApiKeyNotFoundError,
)
from cv_generator_shared.services import ApiKeyService
from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_security import (
    AdminPrincipal,
    AdminSecurityService,
    IssuedAdminSession,
)
from app.config import get_settings
from app.database import get_business_session, get_security_session

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
    del application
    get_settings().validate_security()
    yield


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


def _verify_csrf(request: Request, principal: AdminPrincipal, csrf_token: str) -> None:
    if not _valid_origin(request) or not secrets_compare(
        principal.csrf_token, csrf_token
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


def secrets_compare(first: str, second: str) -> bool:
    import hmac

    return hmac.compare_digest(first, second)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, service: SecurityService) -> HTMLResponse:
    issued = await service.issue_anonymous_session()
    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"csrf_token": issued.csrf_token, "error": None},
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
) -> HTMLResponse:
    settings = get_settings()
    if not _valid_origin(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    issued = await service.login(
        current_token=request.cookies.get(settings.admin_session_cookie_name),
        csrf_token=csrf_token,
        username=username,
        password=password,
        ip_address=_client_ip(request),
    )
    if issued is None:
        response = templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": csrf_token,
                "error": "Identifiants invalides ou connexion temporairement bloquée.",
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        return response
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    _set_session_cookies(response, issued)
    return response


@app.post("/logout")
async def logout(
    request: Request,
    service: SecurityService,
    principal: CurrentAdmin,
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


@app.get("/", response_class=HTMLResponse)
async def key_table(
    request: Request,
    principal: CurrentAdmin,
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
    principal: CurrentAdmin,
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
    principal: CurrentAdmin,
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
    principal: CurrentAdmin,
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
    principal: CurrentAdmin,
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
    principal: CurrentAdmin,
    session: BusinessSession,
    csrf_token: Annotated[str, Form()],
) -> RedirectResponse:
    _verify_csrf(request, principal, csrf_token)
    try:
        await ApiKeyService(session).disable_client(client_id)
    except ApiClientNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return RedirectResponse("/clients", status_code=status.HTTP_303_SEE_OTHER)
