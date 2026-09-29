import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.document_job import DocumentJobStatus, DocumentType


class CreateDocumentRequest(BaseModel):
    """Données nécessaires au démarrage d'une génération de document."""

    avp_number: str = Field(
        min_length=1,
        max_length=128,
        description="Numéro exact de l'avis de vacance de poste OPT.",
        examples=["3134-26-1382/SR"],
    )
    resume: dict[str, Any] = Field(
        description="CV candidat au format JSON Resume.",
        examples=[
            {
                "basics": {
                    "name": "Camille Exemple",
                    "email": "camille@example.nc",
                },
                "skills": [{"name": "Analyse de processus"}],
            }
        ],
    )

    @field_validator("avp_number")
    @classmethod
    def validate_avp_number(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("avp_number ne doit pas être vide")
        return normalized


class DocumentJobCreatedResponse(BaseModel):
    """Confirmation du démarrage d'une génération de document."""

    id: uuid.UUID = Field(description="Identifiant unique du document.")
    status: DocumentJobStatus = Field(description="Statut courant de la génération.")


class DocumentJobStatusResponse(BaseModel):
    """État d'avancement et horodatages d'une génération de document."""

    id: uuid.UUID = Field(description="Identifiant unique du document.")
    status: DocumentJobStatus = Field(description="Statut courant de la génération.")
    created_at: datetime = Field(description="Date de démarrage de la demande.")
    started_at: datetime | None = Field(
        description="Date de début du traitement, si celui-ci a commencé."
    )
    completed_at: datetime | None = Field(
        description="Date de fin du traitement, en succès ou en échec."
    )


class DocumentResultResponse(BaseModel):
    """Contenu source d'un document généré."""

    id: uuid.UUID = Field(description="Identifiant unique du document.")
    type: DocumentType = Field(description="Type de document généré.")
    format: str = Field(
        description="Format source du contenu généré.", examples=["asciidoc"]
    )
    content: str = Field(
        description="Contenu textuel du document au format indiqué.",
        examples=["= Lettre de motivation\n\nObjet : Candidature..."],
    )


# Alias conservé pour les consommateurs utilisant encore le nom historique.
CreateCvDocumentRequest = CreateDocumentRequest


class ErrorDetail(BaseModel):
    """Erreur métier stable exposée dans le champ `detail`."""

    code: str = Field(description="Code technique stable de l'erreur.")
    message: str = Field(description="Description lisible de l'erreur.")


class ErrorResponse(BaseModel):
    """Corps d'une réponse d'erreur HTTP de l'API."""

    detail: ErrorDetail
