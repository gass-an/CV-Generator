import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
from app.admin_security import AdminPrincipal, IssuedAdminSession
from app.database import async_session_factory
from app.main import _parse_expiration
from cv_generator_shared.admin_models import AdminSession
from cv_generator_shared.models import ApiClient, ApiKey
from sqlalchemy import select, update

from conftest import login


def hidden_value(html: str, name: str) -> str:
    match = re.search(rf'name="{name}" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_session_secrets_are_hidden_from_representations() -> None:
    expiry = datetime.now(UTC) + timedelta(hours=1)
    issued = IssuedAdminSession("session-brute", "csrf-brut", expiry)
    principal = AdminPrincipal("admin", "empreinte-session", "csrf-brut")

    assert "session-brute" not in repr(issued)
    assert "csrf-brut" not in repr(issued)
    assert "empreinte-session" not in repr(principal)
    assert "csrf-brut" not in repr(principal)


def test_parse_expiration_uses_configured_timezone_and_preserves_instants() -> None:
    noumea = ZoneInfo("Pacific/Noumea")

    local_value = _parse_expiration("2026-10-03T15:00", timezone=noumea)
    aware_value = _parse_expiration("2026-10-03T15:00:00+02:00", timezone=noumea)

    assert local_value == datetime(2026, 10, 3, 4, 0, tzinfo=UTC)
    assert aware_value == datetime(2026, 10, 3, 13, 0, tzinfo=UTC)
    assert _parse_expiration("", timezone=noumea) is None


@pytest.mark.asyncio
async def test_private_openapi_is_completely_disabled(
    browser: httpx.AsyncClient,
) -> None:
    for path in ("/openapi.json", "/docs", "/redoc"):
        assert (await browser.get(path)).status_code == 404


@pytest.mark.asyncio
async def test_login_session_rotation_expiration_and_logout(
    browser: httpx.AsyncClient,
) -> None:
    assert (await browser.get("/login")).status_code == 200
    anonymous_token = browser.cookies["cv_generator_admin_session"]
    assert (await browser.get("/")).status_code == 401

    csrf = browser.cookies["cv_generator_admin_csrf"]
    bad = await browser.post(
        "/login",
        data={"username": "administrateur", "password": "faux", "csrf_token": csrf},
    )
    assert bad.status_code == 401
    assert "Identifiants invalides" in bad.text
    assert "incorrect" not in bad.text.lower()

    csrf = await login(browser)
    authenticated_token = browser.cookies["cv_generator_admin_session"]
    assert authenticated_token != anonymous_token
    assert (await browser.get("/")).status_code == 200

    response = await browser.post("/logout", data={"csrf_token": csrf})
    assert response.status_code == 303
    browser.cookies.set("cv_generator_admin_session", authenticated_token)
    browser.cookies.set("cv_generator_admin_csrf", csrf)
    assert (await browser.get("/")).status_code == 401

    browser.cookies.clear()
    await login(browser)
    async with async_session_factory() as session, session.begin():
        await session.execute(
            update(AdminSession).values(
                created_at=datetime.now(UTC) - timedelta(hours=2),
                expires_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
    assert (await browser.get("/")).status_code == 401


@pytest.mark.asyncio
async def test_login_csrf_and_persistent_brute_force(
    browser: httpx.AsyncClient,
) -> None:
    await browser.get("/login")
    assert (
        await browser.post(
            "/login",
            data={"username": "administrateur", "password": "mot-de-passe-test"},
        )
    ).status_code == 422

    csrf = browser.cookies["cv_generator_admin_csrf"]
    for _ in range(3):
        response = await browser.post(
            "/login",
            data={"username": "inconnu", "password": "faux", "csrf_token": csrf},
        )
        assert response.status_code == 401
    blocked = await browser.post(
        "/login",
        data={
            "username": "administrateur",
            "password": "mot-de-passe-test",
            "csrf_token": csrf,
        },
    )
    assert blocked.status_code == 401
    assert "temporairement bloquée" in blocked.text


@pytest.mark.asyncio
async def test_csrf_protects_all_state_changes(browser: httpx.AsyncClient) -> None:
    await login(browser)
    for path in (
        "/logout",
        "/keys/00000000-0000-4000-8000-000000000001/revoke",
        "/clients/00000000-0000-4000-8000-000000000001/disable",
    ):
        assert (
            await browser.post(path, data={"csrf_token": "incorrect"})
        ).status_code == 403
    assert (await browser.post("/keys", data={})).status_code in {403, 422}
    assert (await browser.get("/logout")).status_code == 405
    assert (
        await browser.get("/keys/00000000-0000-4000-8000-000000000001/revoke")
    ).status_code == 405
    assert (
        await browser.get("/clients/00000000-0000-4000-8000-000000000001/disable")
    ).status_code == 405


@pytest.mark.asyncio
async def test_create_list_revoke_and_disable_without_secret_leak(
    browser: httpx.AsyncClient,
) -> None:
    csrf = await login(browser)
    form = await browser.get("/keys/new")
    form_token = hidden_value(form.text, "form_token")
    created = await browser.post(
        "/keys",
        data={
            "csrf_token": csrf,
            "form_token": form_token,
            "new_client_name": "Alice Exemple",
            "key_name": "Portable",
            "expires_at": "",
        },
    )
    assert created.status_code == 200
    raw_match = re.search(r'value="(cvg_[^\"]+)"', created.text)
    assert raw_match is not None
    raw_key = raw_match.group(1)
    assert created.headers["cache-control"] == "no-store"
    assert raw_key not in str(browser.cookies)
    assert raw_key not in str(created.url)

    replay = await browser.post(
        "/keys",
        data={
            "csrf_token": csrf,
            "form_token": form_token,
            "new_client_name": "Alice Exemple",
        },
    )
    assert replay.status_code == 409

    table = await browser.get("/")
    assert table.status_code == 200
    assert "Alice Exemple" in table.text
    assert "Portable" in table.text
    assert raw_key not in table.text
    assert "••••" in table.text
    assert "key_hash" not in table.text

    async with async_session_factory() as session:
        client = (await session.scalars(select(ApiClient))).one()
        key = (await session.scalars(select(ApiKey))).one()
        assert raw_key != key.key_hash

    existing_form = await browser.get("/keys/new")
    second = await browser.post(
        "/keys",
        data={
            "csrf_token": csrf,
            "form_token": hidden_value(existing_form.text, "form_token"),
            "client_id": str(client.id),
            "key_name": "Renouvellement",
        },
    )
    assert second.status_code == 200

    revoked = await browser.post(f"/keys/{key.id}/revoke", data={"csrf_token": csrf})
    assert revoked.status_code == 303
    assert "Révoquée" in (await browser.get("/")).text

    disabled = await browser.post(
        f"/clients/{client.id}/disable", data={"csrf_token": csrf}
    )
    assert disabled.status_code == 303
    assert "Désactivé" in (await browser.get("/clients")).text


@pytest.mark.asyncio
async def test_csrf_token_from_another_session_is_rejected() -> None:
    transport = httpx.ASGITransport(app=__import__("app.main", fromlist=["app"]).app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as first,
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as second,
    ):
        first_csrf = await login(first)
        await login(second)
        assert (
            await second.post("/logout", data={"csrf_token": first_csrf})
        ).status_code == 403


@pytest.mark.asyncio
async def test_expired_status_active_filter_and_inactive_owner_rejection(
    browser: httpx.AsyncClient,
) -> None:
    csrf = await login(browser)
    form = await browser.get("/keys/new")
    created = await browser.post(
        "/keys",
        data={
            "csrf_token": csrf,
            "form_token": hidden_value(form.text, "form_token"),
            "new_client_name": "Propriétaire expiré",
            "key_name": "Ancienne clé",
        },
    )
    assert created.status_code == 200
    async with async_session_factory() as session, session.begin():
        client = (await session.scalars(select(ApiClient))).one()
        key = (await session.scalars(select(ApiKey))).one()
        key.created_at = datetime.now(UTC) - timedelta(days=2)
        key.expires_at = datetime.now(UTC) - timedelta(days=1)

    table = await browser.get("/")
    assert "Expirée" in table.text
    assert "Ancienne clé" not in (await browser.get("/?status_filter=active")).text

    disabled = await browser.post(
        f"/clients/{client.id}/disable", data={"csrf_token": csrf}
    )
    assert disabled.status_code == 303
    form = await browser.get("/keys/new")
    refused = await browser.post(
        "/keys",
        data={
            "csrf_token": csrf,
            "form_token": hidden_value(form.text, "form_token"),
            "client_id": str(client.id),
            "key_name": "Interdite",
        },
    )
    assert refused.status_code == 422
    assert "désactivé" in refused.text



@pytest.mark.asyncio
async def test_dates_are_rendered_in_noumea_timezone_and_form_labels_it(
        browser: httpx.AsyncClient,
) -> None:
    csrf = await login(browser)
    form = await browser.get("/keys/new")

    # Date d'expiration dynamique : J+7, heure de Nouméa
    expires_at_dt = (
            datetime.now(ZoneInfo("Pacific/Noumea"))
            + timedelta(days=7)
    ).replace(second=0, microsecond=0)

    expires_at = expires_at_dt.strftime("%Y-%m-%dT%H:%M")
    expected_display = expires_at_dt.strftime("%d/%m/%Y %H:%M")
    expected_utc = expires_at_dt.astimezone(UTC)

    assert "Heure de Nouméa" in form.text

    created = await browser.post(
        "/keys",
        data={
            "csrf_token": csrf,
            "form_token": hidden_value(form.text, "form_token"),
            "new_client_name": "Client fuseau",
            "key_name": "Clé datée",
            "expires_at": expires_at,
        },
    )

    assert created.status_code == 200
    assert expected_display in created.text

    async with async_session_factory() as session, session.begin():
        key = (await session.scalars(select(ApiKey))).one()

        # Vérifie que la date saisie à Nouméa est stockée en UTC
        assert key.expires_at == expected_utc

        key.created_at = datetime(2026, 10, 3, 3, 0, tzinfo=UTC)

        client = (await session.scalars(select(ApiClient))).one()
        client.created_at = datetime(2026, 10, 3, 2, 0, tzinfo=UTC)
        client.is_active = False
        client.disabled_at = datetime(2026, 10, 4, 4, 0, tzinfo=UTC)

    # Vérifie l'affichage des dates à l'heure de Nouméa
    table = await browser.get("/")
    assert "03/10/2026 14:00" in table.text
    assert expected_display in table.text

    clients = await browser.get("/clients")
    assert "03/10/2026 13:00" in clients.text
    assert "04/10/2026 15:00" in clients.text



@pytest.mark.asyncio
async def test_invalid_local_expiration_is_a_form_error(
    browser: httpx.AsyncClient,
) -> None:
    csrf = await login(browser)
    form = await browser.get("/keys/new")
    response = await browser.post(
        "/keys",
        data={
            "csrf_token": csrf,
            "form_token": hidden_value(form.text, "form_token"),
            "new_client_name": "Client invalide",
            "expires_at": "date-invalide",
        },
    )
    assert response.status_code == 422
    async with async_session_factory() as session:
        assert (await session.scalars(select(ApiClient))).all() == []
