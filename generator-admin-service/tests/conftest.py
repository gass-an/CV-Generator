import os
from collections.abc import AsyncIterator

import httpx
import pytest
from argon2 import PasswordHasher
from sqlalchemy import delete, text
from sqlalchemy.engine import make_url

os.environ.setdefault(
    "DATABASE_URL",
    os.getenv(
        "ADMIN_TEST_DATABASE_URL",
        "postgresql+asyncpg://cv_generator:cv_generator@localhost:5432/"
        "cv_generator_admin_test",
    ),
)
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ADMIN_USERNAME", "administrateur")
os.environ.setdefault("ADMIN_PASSWORD_HASH", PasswordHasher().hash("mot-de-passe-test"))
os.environ.setdefault("ADMIN_SESSION_SECRET", "s" * 48)
os.environ.setdefault("ADMIN_LOGIN_MAX_ATTEMPTS", "3")
os.environ.setdefault("ADMIN_BASE_URL", "http://testserver")

from app.database import async_session_factory  # noqa: E402
from app.main import app  # noqa: E402
from cv_generator_shared.admin_models import (  # noqa: E402
    AdminLoginAttempt,
    AdminSession,
)
from cv_generator_shared.models import ApiClient, ApiKey  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def require_dedicated_postgresql() -> None:
    url = make_url(os.environ["DATABASE_URL"])
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_admin_test"
    ):
        pytest.fail(
            "ADMIN_TEST_DATABASE_URL doit désigner une base PostgreSQL dédiée "
            "suffixée _admin_test"
        )


@pytest.fixture(autouse=True)
async def clean_database() -> AsyncIterator[None]:
    async with async_session_factory() as session, session.begin():
        await session.execute(delete(AdminLoginAttempt))
        await session.execute(delete(AdminSession))
        await session.execute(
            text("DELETE FROM document_job WHERE avp_number LIKE 'TEST-ADMIN-%'")
        )
        await session.execute(delete(ApiKey))
        await session.execute(delete(ApiClient))
    yield
    async with async_session_factory() as session, session.begin():
        await session.execute(delete(AdminLoginAttempt))
        await session.execute(delete(AdminSession))
        await session.execute(
            text("DELETE FROM document_job WHERE avp_number LIKE 'TEST-ADMIN-%'")
        )
        await session.execute(delete(ApiKey))
        await session.execute(delete(ApiClient))


@pytest.fixture
async def browser() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        follow_redirects=False,
    ) as client:
        yield client


async def login(browser: httpx.AsyncClient) -> str:
    page = await browser.get("/login")
    assert page.status_code == 200
    csrf = browser.cookies["cv_generator_admin_csrf"]
    response = await browser.post(
        "/login",
        data={
            "username": "administrateur",
            "password": "mot-de-passe-test",
            "csrf_token": csrf,
        },
    )
    assert response.status_code == 303
    return browser.cookies["cv_generator_admin_csrf"]
