import hashlib
import re
import secrets
from dataclasses import dataclass, field
from typing import Protocol

KEY_PREFIX = "cvg"
PUBLIC_PREFIX_BYTES = 9
SECRET_BYTES = 32
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True, slots=True)
class GeneratedKey:
    """Valeur générée en mémoire avant persistance de sa seule empreinte."""

    prefix: str
    value: str = field(repr=False)
    key_hash: str = field(repr=False)


class KeyGenerator(Protocol):
    """Contrat injectable facilitant les tests de collisions."""

    def generate(self) -> GeneratedKey: ...


class SecureKeyGenerator:
    """Génère des clés opaques à haute entropie avec `secrets`."""

    def generate(self) -> GeneratedKey:
        prefix = secrets.token_hex(PUBLIC_PREFIX_BYTES)
        secret = secrets.token_urlsafe(SECRET_BYTES)
        value = f"{KEY_PREFIX}_{prefix}_{secret}"
        return GeneratedKey(
            prefix=prefix,
            value=value,
            key_hash=hash_key(value),
        )


def hash_key(value: str) -> str:
    """Calcule l'empreinte SHA-256 hexadécimale de la clé complète."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def extract_prefix(value: str | None) -> str | None:
    """Extrait le préfixe public d'une clé strictement bien formée."""
    if not value or len(value) > 256:
        return None
    parts = value.split("_", 2)
    if len(parts) != 3 or parts[0] != KEY_PREFIX:
        return None
    prefix, secret = parts[1], parts[2]
    if (
        len(prefix) < 10
        or len(secret) < 43
        or not _TOKEN_PATTERN.fullmatch(prefix)
        or not _TOKEN_PATTERN.fullmatch(secret)
    ):
        return None
    return prefix
