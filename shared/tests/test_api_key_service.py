from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cv_generator_shared.exceptions import (
    ApiClientInactiveError,
    ApiKeyPrefixCollisionError,
)
from cv_generator_shared.models import ApiClient, ApiKey
from cv_generator_shared.repositories import ApiKeyRepository
from cv_generator_shared.security import GeneratedKey, hash_key
from cv_generator_shared.services import ApiKeyService

NOW = datetime(2026, 10, 2, 10, 0, tzinfo=UTC)


class MutableClock:
    def __init__(self, value: datetime = NOW) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class ControlledGenerator:
    def __init__(self, values: Iterator[str]) -> None:
        self._values = values

    def generate(self) -> GeneratedKey:
        value = next(self._values)
        return GeneratedKey(
            prefix=value.split("_", 2)[1], value=value, key_hash=hash_key(value)
        )


class GeneratedSequence:
    def __init__(self, values: Iterator[GeneratedKey]) -> None:
        self._values = values

    def generate(self) -> GeneratedKey:
        return next(self._values)


class InvalidKeyRepository(ApiKeyRepository):
    async def create(self, **values: object) -> ApiKey:
        values["name"] = "   "
        key = ApiKey(**values)
        self._session.add(key)
        await self._session.flush()
        return key


def key_value(prefix: str, fill: str) -> str:
    return f"cvg_{prefix}_{fill * 43}"


@pytest.mark.asyncio
async def test_create_client_and_multiple_distinct_keys(
    session: AsyncSession,
) -> None:
    service = ApiKeyService(session, clock=MutableClock())
    client = await service.create_client(name="  Alice  ")
    first = await service.create_key(client.id, name="Portable")
    second = await service.create_key(client.id)

    assert client.name == "Alice"
    assert first.value != second.value
    assert first.key.prefix != second.key.prefix
    assert "value=" not in repr(first)
    assert first.value not in repr(first)
    assert not hasattr(first.key, "value")
    assert {item.id for item in await service.list_keys(client.id)} == {
        first.key.id,
        second.key.id,
    }
    assert (await service.get_client(client.id)).id == client.id
    assert (await service.list_clients())[0].id == client.id

    stored = (await session.execute(select(ApiKey))).scalars().all()
    assert all(item.key_hash not in {first.value, second.value} for item in stored)
    assert first.value not in repr(stored)
    assert second.value not in repr(stored)


@pytest.mark.asyncio
async def test_verify_valid_incorrect_and_malformed_keys(
    session: AsyncSession,
) -> None:
    service = ApiKeyService(session, clock=MutableClock())
    client = await service.create_client(name="Bob")
    created = await service.create_key(client.id)

    identity = await service.verify_key(created.value)
    assert identity is not None
    assert identity.client_id == client.id
    assert identity.key_id == created.key.id
    assert await service.verify_key(None) is None
    assert await service.verify_key("incorrect") is None
    wrong = created.value[:-1] + ("A" if created.value[-1] != "A" else "B")
    assert await service.verify_key(wrong) is None


@pytest.mark.asyncio
async def test_expiration_revocation_and_client_deactivation(
    session: AsyncSession,
) -> None:
    clock = MutableClock()
    service = ApiKeyService(session, clock=clock)
    client = await service.create_client(name="Chloé")
    expiring = await service.create_key(client.id, expires_at=NOW + timedelta(hours=1))
    revoked = await service.create_key(client.id)
    active = await service.create_key(client.id)

    clock.value = NOW + timedelta(hours=1)
    assert await service.verify_key(expiring.value) is None

    first_revoke = await service.revoke_key(revoked.key.id)
    clock.value += timedelta(hours=1)
    second_revoke = await service.revoke_key(revoked.key.id)
    assert second_revoke.revoked_at == first_revoke.revoked_at
    assert await service.verify_key(revoked.value) is None

    await service.disable_client(client.id)
    assert await service.verify_key(active.value) is None
    with pytest.raises(ApiClientInactiveError):
        await service.create_key(client.id)


@pytest.mark.asyncio
async def test_existing_client_can_receive_a_new_key(
    session: AsyncSession,
) -> None:
    service = ApiKeyService(session, clock=MutableClock())
    client = await service.create_client(name="David")
    old = await service.create_key(client.id)
    await service.revoke_key(old.key.id)
    new = await service.create_key(client.id)

    assert new.key.id != old.key.id
    assert await service.verify_key(old.value) is None
    assert await service.verify_key(new.value) is not None


@pytest.mark.asyncio
async def test_prefix_collision_is_retried_with_a_savepoint(
    session: AsyncSession,
) -> None:
    duplicate = key_value("sameprefix12", "a")
    replacement = key_value("newprefix123", "b")
    generator = ControlledGenerator(iter([duplicate, duplicate, replacement]))
    service = ApiKeyService(session, key_generator=generator, clock=MutableClock())
    client = await service.create_client(name="Emma")

    first = await service.create_key(client.id)
    second = await service.create_key(client.id)
    assert first.key.prefix == "sameprefix12"
    assert second.key.prefix == "newprefix123"


@pytest.mark.asyncio
async def test_key_hash_collision_is_retried_with_a_savepoint(
    session: AsyncSession,
) -> None:
    first_value = key_value("firstprefix1", "a")
    replacement_value = key_value("thirdprefix1", "c")
    duplicate_hash = hash_key(first_value)
    generator = GeneratedSequence(
        iter(
            [
                GeneratedKey("firstprefix1", first_value, duplicate_hash),
                GeneratedKey(
                    "secondprefix", key_value("secondprefix", "b"), duplicate_hash
                ),
                GeneratedKey(
                    "thirdprefix1",
                    replacement_value,
                    hash_key(replacement_value),
                ),
            ]
        )
    )
    service = ApiKeyService(session, key_generator=generator, clock=MutableClock())
    client = await service.create_client(name="Élodie")

    first = await service.create_key(client.id)
    second = await service.create_key(client.id)

    assert first.key.prefix == "firstprefix1"
    assert second.key.prefix == "thirdprefix1"


@pytest.mark.asyncio
async def test_unexpected_integrity_error_is_propagated_and_rolled_back(
    session: AsyncSession,
) -> None:
    service = ApiKeyService(session, clock=MutableClock())
    client = await service.create_client(name="François")
    service._keys = InvalidKeyRepository(session)

    with pytest.raises(IntegrityError):
        await service.create_key(client.id)

    assert not session.in_transaction()
    assert await ApiKeyService(session).list_keys(client.id) == []


@pytest.mark.asyncio
async def test_prefix_collision_attempts_are_bounded(session: AsyncSession) -> None:
    duplicate = key_value("sameprefix12", "a")
    generator = ControlledGenerator(iter([duplicate, duplicate, duplicate]))
    service = ApiKeyService(
        session,
        key_generator=generator,
        clock=MutableClock(),
        max_generation_attempts=2,
    )
    client = await service.create_client(name="Gabrielle")
    await service.create_key(client.id)

    with pytest.raises(ApiKeyPrefixCollisionError):
        await service.create_key(client.id)
    assert len(await service.list_keys(client.id)) == 1


@pytest.mark.asyncio
async def test_database_constraints_and_service_transactions(
    session: AsyncSession,
) -> None:
    service = ApiKeyService(session, clock=MutableClock())
    client = await service.create_client(name="Hélène")
    assert not session.in_transaction()

    session.add(ApiClient(name="   ", created_at=NOW))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()

    created = await service.create_key(client.id)
    session.add(
        ApiKey(
            client_id=client.id,
            prefix="differentprefix1",
            key_hash=(await session.get(ApiKey, created.key.id)).key_hash,
            created_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()

    session.add(
        ApiKey(
            client_id=client.id,
            prefix="dateconstraint1",
            key_hash="f" * 64,
            created_at=NOW,
            expires_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()

    client_model = await session.get(ApiClient, client.id)
    client_model.is_active = False
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()
