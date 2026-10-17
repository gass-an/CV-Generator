from app.core.database import Base as LegacyBase
from app.models import DocumentJob
from cv_generator_shared import ApiClient, ApiKey, Base


def test_legacy_and_shared_models_use_one_declarative_base() -> None:
    assert LegacyBase is Base
    assert DocumentJob.metadata is Base.metadata
    assert ApiClient.metadata is Base.metadata
    assert ApiKey.metadata is Base.metadata
    assert {
        "admin_login_attempt",
        "admin_session",
        "api_client",
        "api_key",
        "document_job",
    } <= set(Base.metadata.tables)


def test_document_job_activity_indexes_are_registered_in_metadata() -> None:
    assert {
        "ix_document_job_completed_at",
        "ix_document_job_created_at_id",
        "ix_document_job_status_created_at",
    } <= {index.name for index in DocumentJob.__table__.indexes}


def test_document_job_schema_uses_nullable_client_ownership() -> None:
    assert DocumentJob.__table__.columns["client_id"].nullable is True
