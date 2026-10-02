import uuid


class ApiKeyManagementError(Exception):
    """Erreur métier de gestion des clients et des clés."""


class ApiClientNotFoundError(ApiKeyManagementError):
    def __init__(self, client_id: uuid.UUID) -> None:
        super().__init__(f"Client d'API introuvable : {client_id}")


class ApiClientInactiveError(ApiKeyManagementError):
    def __init__(self, client_id: uuid.UUID) -> None:
        super().__init__(f"Le client d'API est désactivé : {client_id}")


class ApiKeyNotFoundError(ApiKeyManagementError):
    def __init__(self, key_id: uuid.UUID) -> None:
        super().__init__(f"Clé d'API introuvable : {key_id}")


class ApiKeyPrefixCollisionError(ApiKeyManagementError):
    """Signale l'épuisement du nombre borné de tentatives de génération."""

    def __init__(self) -> None:
        super().__init__("Impossible de générer un préfixe de clé unique")
