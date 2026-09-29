from fastapi import FastAPI

from app.api.v1.router import api_router

OPENAPI_TAGS = [
    {
        "name": "Documents",
        "description": (
            "Création, suivi, récupération et téléchargement des documents générés."
        ),
    },
    {
        "name": "Supervision",
        "description": "Vérification de la disponibilité de l'API.",
    },
]


def create_app() -> FastAPI:
    """Crée l'application HTTP et configure sa documentation OpenAPI."""
    application = FastAPI(
        title="Service de génération de documents HackAVP",
        description=(
            "API de génération asynchrone de CV et de lettres de motivation. "
            "Une requête POST crée un job persistant traité par un worker. Le "
            "client interroge ensuite son statut, récupère le résultat source en "
            "AsciiDoc ou télécharge un fichier DOCX généré à la demande."
        ),
        version="0.1.0",
        openapi_tags=OPENAPI_TAGS,
    )
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
