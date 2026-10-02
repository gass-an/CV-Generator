import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from cv_generator_shared.models import ApiClient, ApiKey


class ApiClientRepository:
    """Persistance des clients, sans gestion de transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, name: str, created_at: datetime) -> ApiClient:
        client = ApiClient(name=name, created_at=created_at)
        self._session.add(client)
        await self._session.flush()
        await self._session.refresh(client)
        return client

    async def get_by_id(
        self, client_id: uuid.UUID, *, for_update: bool = False
    ) -> ApiClient | None:
        statement = select(ApiClient).where(ApiClient.id == client_id)
        if for_update:
            statement = statement.with_for_update()
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def list_all(self) -> list[ApiClient]:
        result = await self._session.execute(
            select(ApiClient).order_by(ApiClient.created_at, ApiClient.id)
        )
        return list(result.scalars())


class ApiKeyRepository:
    """Persistance des empreintes de clés, sans gestion de transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        client_id: uuid.UUID,
        name: str | None,
        prefix: str,
        key_hash: str,
        created_at: datetime,
        expires_at: datetime | None,
    ) -> ApiKey:
        key = ApiKey(
            client_id=client_id,
            name=name,
            prefix=prefix,
            key_hash=key_hash,
            created_at=created_at,
            expires_at=expires_at,
        )
        self._session.add(key)
        await self._session.flush()
        await self._session.refresh(key)
        return key

    async def get_by_prefix(self, prefix: str) -> ApiKey | None:
        statement = (
            select(ApiKey)
            .options(joinedload(ApiKey.client))
            .where(ApiKey.prefix == prefix)
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def get_by_id(
        self, key_id: uuid.UUID, *, for_update: bool = False
    ) -> ApiKey | None:
        statement = select(ApiKey).where(ApiKey.id == key_id)
        if for_update:
            statement = statement.with_for_update()
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def list_for_client(self, client_id: uuid.UUID) -> list[ApiKey]:
        result = await self._session.execute(
            select(ApiKey)
            .where(ApiKey.client_id == client_id)
            .order_by(ApiKey.created_at, ApiKey.id)
        )
        return list(result.scalars())
