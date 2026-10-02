import hmac
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cv_generator_shared.dto import (
    ApiClientData,
    ApiIdentity,
    ApiKeyData,
    ApiKeyWithClientData,
    CreatedApiKey,
    CreatedClientApiKey,
)
from cv_generator_shared.exceptions import (
    ApiClientInactiveError,
    ApiClientNotFoundError,
    ApiKeyNotFoundError,
    ApiKeyPrefixCollisionError,
)
from cv_generator_shared.models import ApiClient, ApiKey
from cv_generator_shared.repositories import ApiClientRepository, ApiKeyRepository
from cv_generator_shared.security import (
    KeyGenerator,
    SecureKeyGenerator,
    extract_prefix,
    hash_key,
)

Clock = Callable[[], datetime]
_RETRYABLE_UNIQUE_CONSTRAINTS = frozenset({"uq_api_key_prefix", "uq_api_key_key_hash"})


def _integrity_constraint_name(error: IntegrityError) -> str | None:
    """Extrait le nom structuré de contrainte exposé par asyncpg."""
    current: BaseException | None = error.orig
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        constraint_name = getattr(current, "constraint_name", None)
        if isinstance(constraint_name, str):
            return constraint_name
        current = current.__cause__ or current.__context__
    return None


def _is_retryable_key_collision(error: IntegrityError) -> bool:
    return _integrity_constraint_name(error) in _RETRYABLE_UNIQUE_CONSTRAINTS


class ApiKeyService:
    """Orchestre les règles métier et possède toutes les transactions."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        key_generator: KeyGenerator | None = None,
        clock: Clock | None = None,
        max_generation_attempts: int = 5,
    ) -> None:
        if max_generation_attempts < 1:
            raise ValueError("Le nombre de tentatives doit être positif")
        self._session = session
        self._clients = ApiClientRepository(session)
        self._keys = ApiKeyRepository(session)
        self._key_generator = key_generator or SecureKeyGenerator()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._max_generation_attempts = max_generation_attempts

    async def create_client(self, *, name: str) -> ApiClientData:
        normalized_name = self._normalize_client_name(name)
        async with self._session.begin():
            client = await self._clients.create(
                name=normalized_name, created_at=self._now()
            )
            return self._client_data(client)

    async def get_client(self, client_id: uuid.UUID) -> ApiClientData:
        async with self._session.begin():
            client = await self._clients.get_by_id(client_id)
            if client is None:
                raise ApiClientNotFoundError(client_id)
            return self._client_data(client)

    async def list_clients(self) -> list[ApiClientData]:
        async with self._session.begin():
            return [self._client_data(item) for item in await self._clients.list_all()]

    async def create_key(
        self,
        client_id: uuid.UUID,
        *,
        name: str | None = None,
        expires_at: datetime | None = None,
    ) -> CreatedApiKey:
        normalized_name = self._normalize_key_name(name)
        now = self._now()
        expires_at = self._normalize_expiration(expires_at, now=now)

        async with self._session.begin():
            client = await self._clients.get_by_id(client_id, for_update=True)
            if client is None:
                raise ApiClientNotFoundError(client_id)
            if not client.is_active:
                raise ApiClientInactiveError(client_id)

            return await self._create_key_in_transaction(
                client=client,
                name=normalized_name,
                expires_at=expires_at,
                now=now,
            )

    async def create_client_with_key(
        self,
        *,
        client_name: str,
        key_name: str | None = None,
        expires_at: datetime | None = None,
    ) -> CreatedClientApiKey:
        """Crée atomiquement un client et sa première clé."""
        normalized_client_name = self._normalize_client_name(client_name)
        normalized_key_name = self._normalize_key_name(key_name)
        now = self._now()
        expires_at = self._normalize_expiration(expires_at, now=now)
        async with self._session.begin():
            client = await self._clients.create(
                name=normalized_client_name,
                created_at=now,
            )
            created_key = await self._create_key_in_transaction(
                client=client,
                name=normalized_key_name,
                expires_at=expires_at,
                now=now,
            )
            return CreatedClientApiKey(
                client=self._client_data(client),
                created_key=created_key,
            )

    async def verify_key(self, value: str | None) -> ApiIdentity | None:
        prefix = extract_prefix(value)
        if prefix is None or value is None:
            return None
        candidate_hash = hash_key(value)
        now = self._now()
        async with self._session.begin():
            key = await self._keys.get_by_prefix(prefix)
            if key is None or not hmac.compare_digest(key.key_hash, candidate_hash):
                return None
            if key.revoked_at is not None:
                return None
            if key.expires_at is not None and self._as_utc(key.expires_at) <= now:
                return None
            if not key.client.is_active:
                return None
            return ApiIdentity(
                client_id=key.client_id,
                key_id=key.id,
                client_name=key.client.name,
            )

    async def list_keys(self, client_id: uuid.UUID) -> list[ApiKeyData]:
        async with self._session.begin():
            client = await self._clients.get_by_id(client_id)
            if client is None:
                raise ApiClientNotFoundError(client_id)
            keys = await self._keys.list_for_client(client_id)
            return [self._key_data(item) for item in keys]

    async def list_all_keys(
        self,
        *,
        offset: int = 0,
        limit: int | None = None,
        active_only: bool = False,
    ) -> list[ApiKeyWithClientData]:
        """Liste toutes les clés avec les métadonnées utiles du propriétaire."""
        if offset < 0 or (limit is not None and limit < 1):
            raise ValueError("La pagination des clés est invalide")
        async with self._session.begin():
            keys = await self._keys.list_all_with_clients(
                offset=offset,
                limit=limit,
                active_at=self._now() if active_only else None,
            )
            return [
                ApiKeyWithClientData(
                    key=self._key_data(item),
                    client_name=item.client.name,
                    client_is_active=item.client.is_active,
                )
                for item in keys
            ]

    async def revoke_key(self, key_id: uuid.UUID) -> ApiKeyData:
        async with self._session.begin():
            key = await self._keys.get_by_id(key_id, for_update=True)
            if key is None:
                raise ApiKeyNotFoundError(key_id)
            if key.revoked_at is None:
                key.revoked_at = self._now()
                await self._session.flush()
            return self._key_data(key)

    async def disable_client(self, client_id: uuid.UUID) -> ApiClientData:
        async with self._session.begin():
            client = await self._clients.get_by_id(client_id, for_update=True)
            if client is None:
                raise ApiClientNotFoundError(client_id)
            if client.is_active:
                client.is_active = False
                client.disabled_at = self._now()
                await self._session.flush()
            return self._client_data(client)

    def _now(self) -> datetime:
        return self._as_utc(self._clock())

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Une date doit inclure un fuseau horaire")
        return value.astimezone(UTC)

    async def _create_key_in_transaction(
        self,
        *,
        client: ApiClient,
        name: str | None,
        expires_at: datetime | None,
        now: datetime,
    ) -> CreatedApiKey:
        for _ in range(self._max_generation_attempts):
            generated = self._key_generator.generate()
            try:
                async with self._session.begin_nested():
                    key = await self._keys.create(
                        client_id=client.id,
                        name=name,
                        prefix=generated.prefix,
                        key_hash=generated.key_hash,
                        created_at=now,
                        expires_at=expires_at,
                    )
            except IntegrityError as error:
                if not _is_retryable_key_collision(error):
                    raise
                continue
            return CreatedApiKey(key=self._key_data(key), value=generated.value)
        raise ApiKeyPrefixCollisionError

    @staticmethod
    def _normalize_client_name(name: str) -> str:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Le nom du client ne peut pas être vide")
        if len(normalized_name) > 200:
            raise ValueError("Le nom du client dépasse 200 caractères")
        return normalized_name

    @staticmethod
    def _normalize_key_name(name: str | None) -> str | None:
        normalized_name = name.strip() if name is not None else None
        if normalized_name == "":
            raise ValueError("Le libellé de la clé ne peut pas être vide")
        if normalized_name is not None and len(normalized_name) > 200:
            raise ValueError("Le libellé de la clé dépasse 200 caractères")
        return normalized_name

    def _normalize_expiration(
        self, expires_at: datetime | None, *, now: datetime
    ) -> datetime | None:
        if expires_at is None:
            return None
        normalized_expiration = self._as_utc(expires_at)
        if normalized_expiration <= now:
            raise ValueError("L'expiration doit être postérieure à la création")
        return normalized_expiration

    @staticmethod
    def _client_data(client: ApiClient) -> ApiClientData:
        return ApiClientData(
            id=client.id,
            name=client.name,
            is_active=client.is_active,
            created_at=client.created_at,
            disabled_at=client.disabled_at,
        )

    @staticmethod
    def _key_data(key: ApiKey) -> ApiKeyData:
        return ApiKeyData(
            id=key.id,
            client_id=key.client_id,
            name=key.name,
            prefix=key.prefix,
            created_at=key.created_at,
            expires_at=key.expires_at,
            revoked_at=key.revoked_at,
        )
