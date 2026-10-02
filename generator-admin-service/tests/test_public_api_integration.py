import os
import re
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from app.database import async_session_factory
from cv_generator_shared.models import ApiClient, ApiKey
from sqlalchemy import select

from conftest import login
from test_admin_http import hidden_value

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "generator-service"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def public_api_url() -> Iterator[str]:
    port = _free_port()
    environment = os.environ.copy()
    environment["DATABASE_URL"] = os.environ["DATABASE_URL"]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=BACKEND_ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if process.poll() is not None:
                pytest.fail("Le backend public de test n'a pas démarré")
            try:
                if httpx.get(f"{url}/api/v1/health", timeout=0.2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.05)
        else:
            pytest.fail("Le backend public de test n'est pas devenu disponible")
        yield url
    finally:
        process.terminate()
        process.wait(timeout=10)


def _raw_key(response: httpx.Response) -> str:
    match = re.search(r'value="(cvg_[^\"]+)"', response.text)
    assert match is not None
    return match.group(1)


async def _create_key(
    browser: httpx.AsyncClient,
    csrf: str,
    *,
    client_id: str = "",
    client_name: str = "",
    key_name: str,
) -> str:
    form = await browser.get("/keys/new")
    response = await browser.post(
        "/keys",
        data={
            "csrf_token": csrf,
            "form_token": hidden_value(form.text, "form_token"),
            "client_id": client_id,
            "new_client_name": client_name,
            "key_name": key_name,
        },
    )
    assert response.status_code == 200
    return _raw_key(response)


@pytest.mark.asyncio
async def test_admin_key_is_immediately_shared_with_public_api(
    browser: httpx.AsyncClient,
    public_api_url: str,
) -> None:
    csrf = await login(browser)
    first_key = await _create_key(
        browser,
        csrf,
        client_name="Client parcours complet",
        key_name="Première clé",
    )
    async with async_session_factory() as session:
        client = (await session.scalars(select(ApiClient))).one()
        first_record = (await session.scalars(select(ApiKey))).one()

    async with httpx.AsyncClient(base_url=public_api_url) as public:
        created = await public.post(
            "/api/v1/documents/cv",
            headers={"X-API-Key": first_key},
            json={"avp_number": "TEST-ADMIN-001", "resume": {"basics": {}}},
        )
        assert created.status_code == 202
        document_id = created.json()["id"]

        second_key = await _create_key(
            browser,
            csrf,
            client_id=str(client.id),
            key_name="Deuxième clé",
        )
        assert (
            await public.get(
                f"/api/v1/documents/{document_id}/status",
                headers={"X-API-Key": second_key},
            )
        ).status_code == 200

        revoked = await browser.post(
            f"/keys/{first_record.id}/revoke", data={"csrf_token": csrf}
        )
        assert revoked.status_code == 303
        assert (
            await public.get(
                f"/api/v1/documents/{document_id}/status",
                headers={"X-API-Key": first_key},
            )
        ).status_code == 401
        assert (
            await public.get(
                f"/api/v1/documents/{document_id}/status",
                headers={"X-API-Key": second_key},
            )
        ).status_code == 200

        disabled = await browser.post(
            f"/clients/{client.id}/disable", data={"csrf_token": csrf}
        )
        assert disabled.status_code == 303
        for key in (first_key, second_key):
            assert (
                await public.get(
                    f"/api/v1/documents/{document_id}/status",
                    headers={"X-API-Key": key},
                )
            ).status_code == 401
