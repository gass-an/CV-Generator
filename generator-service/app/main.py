import os

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
    app_version = os.environ.get("APP_VERSION", "").strip()

    if not app_version:
        raise RuntimeError(
            "APP_VERSION doit être définie dans l'environnement"
        )

    application = FastAPI(
        title="Service de génération de documents HackAVP",
        description=(
            "API de génération asynchrone de CV et de lettres de motivation. "
            "Une requête POST démarre la génération asynchrone d'un document. "
            "L'API retourne immédiatement un identifiant qui permet de suivre "
            "l'avancement, de récupérer le résultat source en AsciiDoc puis de "
            "télécharger le document au format DOCX."
        ),
        version=app_version.removeprefix("v"),
        openapi_tags=OPENAPI_TAGS,
    )

    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
