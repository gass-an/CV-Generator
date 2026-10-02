from app.core.database import Base as LegacyBase
from app.models import DocumentJob
from cv_generator_shared import ApiClient, ApiKey, Base


def test_legacy_and_shared_models_use_one_declarative_base() -> None:
    assert LegacyBase is Base
    assert DocumentJob.metadata is Base.metadata
    assert ApiClient.metadata is Base.metadata
    assert ApiKey.metadata is Base.metadata
    assert {"document_job", "api_client", "api_key"} <= set(Base.metadata.tables)


def test_document_job_schema_does_not_gain_client_ownership() -> None:
    assert "client_id" not in DocumentJob.__table__.columns
