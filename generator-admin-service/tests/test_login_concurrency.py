import asyncio

import pytest
from app.admin_security import AdminSecurityService
from app.config import get_settings
from app.database import async_session_factory
from cv_generator_shared.admin_models import AdminLoginAttempt
from sqlalchemy import delete, func, select


async def failed_login(ip_address: str, username: str) -> None:
    async with async_session_factory() as session:
        service = AdminSecurityService(session, get_settings())
        anonymous = await service.issue_anonymous_session()
        result = await service.login(
            current_token=anonymous.token,
            csrf_token=anonymous.csrf_token,
            username=username,
            password="mot-de-passe-incorrect",
            ip_address=ip_address,
        )
        assert result is None


async def attempt_count() -> int:
    async with async_session_factory() as session:
        return int(await session.scalar(select(func.count(AdminLoginAttempt.id))) or 0)


@pytest.mark.asyncio
async def test_concurrent_limit_is_atomic_by_ip_and_account() -> None:
    settings = get_settings()
    number_of_requests = settings.admin_login_max_attempts + 5

    await asyncio.wait_for(
        asyncio.gather(
            *(
                failed_login("192.0.2.10", f"compte-{index}")
                for index in range(number_of_requests)
            )
        ),
        timeout=30,
    )
    assert await attempt_count() == settings.admin_login_max_attempts

    async with async_session_factory() as session, session.begin():
        await session.execute(delete(AdminLoginAttempt))

    await asyncio.wait_for(
        asyncio.gather(
            *(
                failed_login(f"192.0.2.{index + 20}", "même-compte")
                for index in range(number_of_requests)
            )
        ),
        timeout=30,
    )
    assert await attempt_count() == settings.admin_login_max_attempts
