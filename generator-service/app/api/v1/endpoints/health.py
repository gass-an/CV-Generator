from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter(tags=["Supervision"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Vérifier la disponibilité de l'API",
    description="Retourne un état minimal sans interroger les services externes.",
    response_description="L'API répond aux requêtes HTTP.",
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
