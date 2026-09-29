import uuid


class GeneratorServiceError(Exception):
    """Exception de base pour les erreurs métier attendues du service."""


class DocumentJobNotFoundError(GeneratorServiceError):
    def __init__(self, job_id: uuid.UUID) -> None:
        super().__init__(f"Le job de génération {job_id} est introuvable")


class DocumentJobNotReadyError(GeneratorServiceError):
    """Le résultat a été demandé avant la fin du traitement."""


class DocumentGenerationFailedError(GeneratorServiceError):
    """Le résultat demandé appartient à un job en échec."""


class DocumentResultUnavailableError(GeneratorServiceError):
    """Un job terminé ne possède pas de résultat AsciiDoc exploitable."""
