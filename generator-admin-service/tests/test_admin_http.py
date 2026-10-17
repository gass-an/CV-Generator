import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
from app.admin_security import AdminPrincipal, IssuedAdminSession
from app.database import async_session_factory
from app.main import _parse_expiration, _safe_next_path
from cv_generator_shared.admin_models import AdminLoginAttempt, AdminSession
from cv_generator_shared.models import ApiClient, ApiKey
from sqlalchemy import select, update

from conftest import login

ROOT = Path(__file__).resolve().parents[1]


def hidden_value(html: str, name: str) -> str:
    match = re.search(rf'name="{name}" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_session_secrets_are_hidden_from_representations() -> None:
    expiry = datetime(2030, 1, 1, tzinfo=UTC)
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


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/", "/"),
        ("/clients", "/clients"),
        ("/clients?status=active&page=2", "/clients?status=active&page=2"),
        ("https://example.com/admin", "/"),
        ("http://example.com/admin", "/"),
        ("//example.com/admin", "/"),
        (r"/\example.com/admin", "/"),
        ("/clients\nadmin", "/"),
        ("/clients\radmin", "/"),
        ("/clients\tadmin", "/"),
        ("/clients\x7fadmin", "/"),
    ],
)
def test_safe_next_path_accepts_only_safe_local_destinations(
    value: str, expected: str
) -> None:
    assert _safe_next_path(value) == expected


@pytest.mark.asyncio
async def test_private_openapi_is_completely_disabled(
    browser: httpx.AsyncClient,
) -> None:
    for path in ("/openapi.json", "/docs", "/redoc"):
        assert (await browser.get(path)).status_code == 404


@pytest.mark.asyncio
async def test_admin_interface_exposes_brand_navigation_and_theme_controls(
    browser: httpx.AsyncClient,
) -> None:
    login_page = await browser.get("/login")
    assert "<title>Connexion — CV-Generator Admin</title>" in login_page.text
    assert 'href="/static/favicon.png"' in login_page.text
    assert 'name="theme-color" content="#f7f9fc" data-theme-color' in login_page.text
    assert 'src="/static/cv-generator.png"' in login_page.text
    assert 'href="#contenu-principal"' in login_page.text
    for theme in ("light", "dark", "system"):
        assert f'data-theme-value="{theme}"' in login_page.text

    script = await browser.get("/static/admin.js")
    stylesheet = await browser.get("/static/admin.css")
    favicon = await browser.get("/static/favicon.png")
    assert script.status_code == stylesheet.status_code == favicon.status_code == 200
    assert ':root[data-theme="dark"]' in stylesheet.text
    assert "prefers-color-scheme: dark" in stylesheet.text
    assert ".topbar-actions .theme-switcher { display: none; }" not in stylesheet.text
    assert ".button[hidden] { display: none; }" in stylesheet.text

    await login(browser)
    home = await browser.get("/")
    assert 'aria-current="page">Clés API</a>' in home.text
    assert 'aria-label="Navigation de l’administration"' in home.text
    assert 'action="/logout"' in home.text
    assert home.headers["content-security-policy"].startswith("default-src 'self'")
    assert "'unsafe-inline'" not in home.headers["content-security-policy"]


@pytest.mark.asyncio
async def test_login_session_rotation_expiration_and_logout(
    browser: httpx.AsyncClient,
) -> None:
    anonymous_root = await browser.get("/")
    assert anonymous_root.status_code == 303
    assert anonymous_root.headers["location"] == "/login?next=%2F"

    assert (await browser.get("/login")).status_code == 200
    anonymous_token = browser.cookies["cv_generator_admin_session"]

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
    authenticated_login = await browser.get("/login")
    assert authenticated_login.status_code == 303
    assert authenticated_login.headers["location"] == "/"

    response = await browser.post("/logout", data={"csrf_token": csrf})
    assert response.status_code == 303
    browser.cookies.set("cv_generator_admin_session", authenticated_token)
    browser.cookies.set("cv_generator_admin_csrf", csrf)
    logged_out = await browser.get("/")
    assert logged_out.status_code == 303
    assert logged_out.headers["location"].startswith("/login?")

    browser.cookies.clear()
    await login(browser)
    async with async_session_factory() as session, session.begin():
        await session.execute(
            update(AdminSession).values(
                created_at=datetime(2020, 1, 1, tzinfo=UTC),
                expires_at=datetime(2020, 1, 1, 1, tzinfo=UTC),
            )
        )
    expired = await browser.get("/")
    assert expired.status_code == 303
    assert "expired=1" in expired.headers["location"]

    login_page = await browser.get(expired.headers["location"])
    assert login_page.status_code == 200
    assert "session a expiré" in login_page.text
    renewed_csrf = browser.cookies["cv_generator_admin_csrf"]
    reconnected = await browser.post(
        "/login",
        data={
            "username": "administrateur",
            "password": "mot-de-passe-test",
            "csrf_token": renewed_csrf,
            "next": "/",
        },
    )
    assert reconnected.status_code == 303
    assert (await browser.get("/")).status_code == 200


@pytest.mark.asyncio
async def test_login_honors_only_safe_local_next_paths(
    browser: httpx.AsyncClient,
) -> None:
    page = await browser.get("/login?next=/clients")
    csrf = browser.cookies["cv_generator_admin_csrf"]
    redirected = await browser.post(
        "/login",
        data={
            "username": "administrateur",
            "password": "mot-de-passe-test",
            "csrf_token": csrf,
            "next": hidden_value(page.text, "next"),
        },
    )
    assert redirected.headers["location"] == "/clients"

    await browser.post(
        "/logout", data={"csrf_token": browser.cookies["cv_generator_admin_csrf"]}
    )
    external = await browser.get("/login?next=https://example.com/phishing")
    assert hidden_value(external.text, "next") == "/"


@pytest.mark.asyncio
async def test_invalid_session_and_csrf_can_recover_without_clearing_cookies(
    browser: httpx.AsyncClient,
) -> None:
    browser.cookies.set(
        "cv_generator_admin_session", "session-invalide", domain="testserver.local"
    )
    browser.cookies.set(
        "cv_generator_admin_csrf", "csrf-invalide", domain="testserver.local"
    )

    protected = await browser.get("/clients")
    assert protected.status_code == 303
    login_page = await browser.get(protected.headers["location"])
    first_csrf = browser.cookies["cv_generator_admin_csrf"]
    invalid_csrf = await browser.post(
        "/login",
        data={
            "username": "administrateur",
            "password": "mot-de-passe-test",
            "csrf_token": "csrf-obsolete",
            "next": hidden_value(login_page.text, "next"),
        },
    )
    assert invalid_csrf.status_code == 403
    assert "session du formulaire a expiré" in invalid_csrf.text
    assert "Identifiants invalides" not in invalid_csrf.text
    assert 'value="administrateur"' in invalid_csrf.text
    replacement_csrf = browser.cookies["cv_generator_admin_csrf"]
    assert replacement_csrf != first_csrf

    reconnected = await browser.post(
        "/login",
        data={
            "username": "administrateur",
            "password": "mot-de-passe-test",
            "csrf_token": replacement_csrf,
            "next": hidden_value(invalid_csrf.text, "next"),
        },
    )
    assert reconnected.status_code == 303
    assert reconnected.headers["location"] == "/clients"
    assert (await browser.get("/clients")).status_code == 200


@pytest.mark.asyncio
async def test_expired_anonymous_session_is_renewed_before_login(
    browser: httpx.AsyncClient,
) -> None:
    page = await browser.get("/login?next=/clients")
    original_csrf = hidden_value(page.text, "csrf_token")

    async with async_session_factory() as session, session.begin():
        expired_at = datetime(2020, 1, 1, 1, tzinfo=UTC)
        await session.execute(
            update(AdminSession).values(
                created_at=expired_at - timedelta(hours=1), expires_at=expired_at
            )
        )

    stale = await browser.post(
        "/login",
        data={
            "username": "administrateur",
            "password": "mot-de-passe-test",
            "csrf_token": original_csrf,
            "next": "/clients",
        },
    )
    assert stale.status_code == 403
    assert "n’ont pas été vérifiés" in stale.text
    async with async_session_factory() as session:
        assert (await session.scalars(select(AdminLoginAttempt))).all() == []

    renewal = await browser.get("/login/csrf")
    assert renewal.status_code == 200
    payload = renewal.json()
    assert payload["csrf_token"] != original_csrf
    assert browser.cookies["cv_generator_admin_csrf"] == payload["csrf_token"]

    connected = await browser.post(
        "/login",
        data={
            "username": "administrateur",
            "password": "mot-de-passe-test",
            "csrf_token": payload["csrf_token"],
            "next": "/clients",
        },
    )
    assert connected.status_code == 303
    assert connected.headers["location"] == "/clients"


@pytest.mark.asyncio
async def test_login_csrf_renewal_keeps_origin_and_authentication_protections(
    browser: httpx.AsyncClient,
) -> None:
    await browser.get("/login")
    rejected = await browser.get(
        "/login/csrf",
        headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
    )
    assert rejected.status_code == 403

    await login(browser)
    authenticated_token = browser.cookies["cv_generator_admin_session"]
    authenticated_csrf = browser.cookies["cv_generator_admin_csrf"]
    renewal = await browser.get(
        "/login/csrf",
        headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
    )
    assert renewal.status_code == 409
    assert browser.cookies["cv_generator_admin_session"] == authenticated_token
    assert browser.cookies["cv_generator_admin_csrf"] == authenticated_csrf


@pytest.mark.asyncio
async def test_login_csrf_renewal_handles_sequential_tabs(
    browser: httpx.AsyncClient,
) -> None:
    first_tab = await browser.get("/login?next=/clients")
    first_tab_csrf = hidden_value(first_tab.text, "csrf_token")
    second_tab = await browser.get("/login")
    second_tab_csrf = hidden_value(second_tab.text, "csrf_token")
    assert second_tab_csrf != first_tab_csrf

    first_renewal = await browser.get("/login/csrf")
    renewed_csrf = first_renewal.json()["csrf_token"]
    connected = await browser.post(
        "/login",
        data={
            "username": "administrateur",
            "password": "mot-de-passe-test",
            "csrf_token": renewed_csrf,
            "next": "/clients",
        },
    )
    assert connected.status_code == 303
    authenticated_token = browser.cookies["cv_generator_admin_session"]

    second_renewal = await browser.get("/login/csrf")
    assert second_renewal.status_code == 409
    assert browser.cookies["cv_generator_admin_session"] == authenticated_token


def test_admin_javascript_behaviors() -> None:
    subprocess.run(
        ["node", "tests/test_admin_js.mjs"],
        cwd=ROOT,
        check=True,
    )


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
        csrf = browser.cookies["cv_generator_admin_csrf"]
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
        key.created_at = datetime(2020, 1, 1, tzinfo=UTC)
        key.expires_at = datetime(2020, 1, 2, tzinfo=UTC)

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

    expires_at_dt = datetime(2099, 6, 15, 9, 30, tzinfo=ZoneInfo("Pacific/Noumea"))

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
