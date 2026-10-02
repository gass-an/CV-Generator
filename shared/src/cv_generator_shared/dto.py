import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ApiClientData:
    """Métadonnées publiques d'un client d'API."""

    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime
    disabled_at: datetime | None


@dataclass(frozen=True, slots=True)
class ApiKeyData:
    """Métadonnées d'une clé ne contenant jamais sa valeur complète."""

    id: uuid.UUID
    client_id: uuid.UUID
    name: str | None
    prefix: str
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class ApiKeyWithClientData:
    """Métadonnées d'une clé accompagnées de son propriétaire."""

    key: ApiKeyData
    client_name: str
    client_is_active: bool


@dataclass(frozen=True, slots=True)
class CreatedApiKey:
    """Résultat éphémère remis une seule fois lors de la création."""

    key: ApiKeyData
    value: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CreatedClientApiKey:
    """Client et première clé créés dans une transaction atomique."""

    client: ApiClientData
    created_key: CreatedApiKey


@dataclass(frozen=True, slots=True)
class ApiIdentity:
    """Identité métier obtenue après vérification d'une clé."""

    client_id: uuid.UUID
    key_id: uuid.UUID
    client_name: str
