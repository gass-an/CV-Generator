from typing import Annotated

from cv_generator_shared.dto import ApiIdentity
from cv_generator_shared.services import ApiKeyService
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session

api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="X-API-Key",
    auto_error=False,
)

ApiKeyValue = Annotated[str | None, Security(api_key_header)]


async def get_api_key_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiKeyService:
    """Construit le service partagé avec une session sans transaction active."""
    return ApiKeyService(session)


async def require_api_identity(
    api_key: ApiKeyValue,
    service: Annotated[ApiKeyService, Depends(get_api_key_service)],
) -> ApiIdentity:
    """Authentifie une requête sans révéler la cause précise d'un refus."""
    identity = await service.verify_key(api_key)
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_api_key",
                "message": "Clé API absente ou invalide",
            },
        )
    return identity


AuthenticatedIdentity = Annotated[ApiIdentity, Depends(require_api_identity)]
