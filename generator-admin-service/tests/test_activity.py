import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.activity import ActivityFilters, AdminActivityService
from app.config import get_settings
from app.database import async_session_factory
from cv_generator_shared.document_jobs import (
    DocumentJob,
    DocumentJobStatus,
    DocumentType,
)
from cv_generator_shared.models import ApiClient

from conftest import login


def make_job(
    *,
    client_id: uuid.UUID | None,
    document_type: DocumentType = DocumentType.CV,
    status: DocumentJobStatus = DocumentJobStatus.PENDING,
    avp_number: str,
    created_at: datetime,
    candidate_name: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> DocumentJob:
    basics = {"email": "ne-doit-pas-etre-expose@example.test"}
    if candidate_name is not None:
        basics["name"] = candidate_name
    return DocumentJob(
        client_id=client_id,
        document_type=document_type,
        status=status,
        avp_number=avp_number,
        resume_data={"basics": basics, "work": [{"name": "Donnée sensible"}]},
        created_at=created_at,
        started_at=started_at,
        completed_at=completed_at,
        updated_at=completed_at or started_at or created_at,
    )


@pytest.mark.asyncio
async def test_activity_routes_require_an_authenticated_admin(
    browser: httpx.AsyncClient,
) -> None:
    page = await browser.get("/activity")
    assert page.status_code == 303
    assert page.headers["location"] == "/login?next=%2Factivity"
    assert (await browser.get("/activity/data")).status_code == 401


@pytest.mark.asyncio
async def test_activity_attributes_jobs_and_counts_in_admin_timezone(
    browser: httpx.AsyncClient,
) -> None:
    now = datetime(2026, 10, 17, 1, 30, tzinfo=UTC)  # 12 h 30 à Nouméa
    async with async_session_factory() as session, session.begin():
        active = ApiClient(name="Propriétaire actif")
        disabled = ApiClient(
            name="Propriétaire désactivé",
            is_active=False,
            disabled_at=now - timedelta(days=1),
        )
        session.add_all([active, disabled])
        await session.flush()
        session.add_all(
            [
                make_job(
                    client_id=active.id,
                    status=DocumentJobStatus.PENDING,
                    avp_number="TEST-ADMIN-ACT-001",
                    created_at=now - timedelta(minutes=5),
                    candidate_name="Alice Exemple",
                ),
                make_job(
                    client_id=disabled.id,
                    document_type=DocumentType.COVER_LETTER,
                    status=DocumentJobStatus.PROCESSING,
                    avp_number="TEST-ADMIN-ACT-002",
                    created_at=now - timedelta(minutes=10),
                    started_at=now - timedelta(minutes=8),
                ),
                make_job(
                    client_id=active.id,
                    document_type=DocumentType.INTERVIEW_PREP,
                    status=DocumentJobStatus.COMPLETED,
                    avp_number="TEST-ADMIN-ACT-003",
                    created_at=now - timedelta(hours=1),
                    started_at=now - timedelta(minutes=50),
                    completed_at=now - timedelta(minutes=20),
                ),
                make_job(
                    client_id=None,
                    status=DocumentJobStatus.FAILED,
                    avp_number="TEST-ADMIN-ACT-004",
                    created_at=now - timedelta(hours=2),
                    started_at=now - timedelta(hours=1, minutes=50),
                    completed_at=now - timedelta(minutes=30),
                ),
                make_job(
                    client_id=None,
                    status=DocumentJobStatus.FAILED,
                    avp_number="TEST-ADMIN-ACT-OLD",
                    created_at=now - timedelta(days=2),
                    completed_at=now - timedelta(days=1),
                ),
            ]
        )

    async with async_session_factory() as session:
        snapshot = await AdminActivityService(
            session, get_settings().timezone
        ).snapshot(ActivityFilters(), now=now)
    assert snapshot.counters.pending == 1
    assert snapshot.counters.processing == 1
    assert snapshot.counters.completed_today == 1
    assert snapshot.counters.failed_today == 1
    assert [job.avp_number for job in snapshot.history[:2]] == [
        "TEST-ADMIN-ACT-001",
        "TEST-ADMIN-ACT-002",
    ]
    assert snapshot.history[1].owner_name == "Propriétaire désactivé"
    assert snapshot.history[1].owner_active is False
    orphan = next(job for job in snapshot.history if job.client_id is None)
    assert orphan.owner_name is None

    await login(browser)
    page = await browser.get("/activity")
    assert page.status_code == 200
    assert "Alice Exemple" in page.text
    assert "Propriétaire inconnu" in page.text
    assert "Donnée sensible" not in page.text
    assert "ne-doit-pas-etre-expose" not in page.text
    assert 'aria-current="page">Activité</a>' in page.text

    payload = (await browser.get("/activity/data")).json()
    serialized = str(payload)
    assert "Alice Exemple" in serialized
    assert "Donnée sensible" not in serialized
    assert "ne-doit-pas-etre-expose" not in serialized
    assert "error_message" not in serialized


@pytest.mark.asyncio
async def test_activity_filters_sorting_and_server_side_pagination(
    browser: httpx.AsyncClient,
) -> None:
    now = datetime.now(UTC)
    async with async_session_factory() as session, session.begin():
        first = ApiClient(name="Premier propriétaire")
        second = ApiClient(name="Second propriétaire")
        session.add_all([first, second])
        await session.flush()
        for index in range(28):
            session.add(
                make_job(
                    client_id=first.id if index < 27 else second.id,
                    document_type=DocumentType.CV
                    if index % 2 == 0
                    else DocumentType.COVER_LETTER,
                    status=DocumentJobStatus.FAILED
                    if index % 3 == 0
                    else DocumentJobStatus.COMPLETED,
                    avp_number=f"TEST-ADMIN-PAGE-{index:02d}",
                    created_at=now - timedelta(minutes=index),
                    completed_at=now - timedelta(minutes=index),
                )
            )

    await login(browser)
    first_page = (
        await browser.get(
            "/activity/data",
            params={"client_id": str(first.id), "page": 1},
        )
    ).json()
    second_page = (
        await browser.get(
            "/activity/data",
            params={"client_id": str(first.id), "page": 2},
        )
    ).json()
    assert first_page["pagination"] == {
        "page": 1,
        "page_count": 2,
        "page_size": 25,
        "total": 27,
    }
    assert len(first_page["history"]) == 25
    assert len(second_page["history"]) == 2
    assert first_page["history"][0]["avp_number"] == "TEST-ADMIN-PAGE-00"
    assert second_page["history"][-1]["avp_number"] == "TEST-ADMIN-PAGE-26"

    filtered = await browser.get(
        "/activity/data",
        params={
            "client_id": str(first.id),
            "document_type": "cover_letter",
            "status": "failed",
            "avp_number": "TEST-ADMIN-PAGE-03",
            "created_from": now.astimezone(get_settings().timezone).date().isoformat(),
            "created_to": now.astimezone(get_settings().timezone).date().isoformat(),
        },
    )
    assert filtered.status_code == 200
    assert [item["avp_number"] for item in filtered.json()["history"]] == [
        "TEST-ADMIN-PAGE-03"
    ]
    assert (await browser.get("/activity/data?status=unknown")).status_code == 422
