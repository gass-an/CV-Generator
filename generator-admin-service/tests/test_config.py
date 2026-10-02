import pytest
from app.config import AdminSettings
from argon2 import PasswordHasher


def test_production_requires_secure_cookie_and_valid_argon2id() -> None:
    valid_hash = PasswordHasher().hash("mot-de-passe")
    settings = AdminSettings(
        app_env="production",
        admin_username="admin",
        admin_password_hash=valid_hash,
        admin_session_secret="s" * 32,
        admin_cookie_secure=False,
    )
    with pytest.raises(RuntimeError, match="ADMIN_COOKIE_SECURE"):
        settings.validate_security()

    insecure_url = settings.model_copy(
        update={"admin_cookie_secure": True, "admin_base_url": "http://admin.test"}
    )
    with pytest.raises(RuntimeError, match="HTTPS"):
        insecure_url.validate_security()

    invalid_hash = settings.model_copy(
        update={"app_env": "development", "admin_password_hash": "invalide"}
    )
    with pytest.raises(RuntimeError, match="Argon2"):
        invalid_hash.validate_security()


def test_required_security_configuration_has_no_default_credentials() -> None:
    settings = AdminSettings(
        admin_username=None,
        admin_password_hash=None,
        admin_session_secret=None,
    )
    with pytest.raises(RuntimeError, match="ADMIN_USERNAME"):
        settings.validate_security()


def test_unknown_admin_timezone_is_rejected() -> None:
    settings = AdminSettings(admin_timezone="Fuseau/Inconnu")
    with pytest.raises(RuntimeError, match="ADMIN_TIMEZONE est inconnu"):
        settings.validate_security()
