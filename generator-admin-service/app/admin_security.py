import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cv_generator_shared.admin_models import AdminLoginAttempt, AdminSession
from sqlalchemy import BigInteger, bindparam, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AdminSettings


@dataclass(frozen=True, slots=True)
class IssuedAdminSession:
    token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AdminPrincipal:
    username: str
    token_hash: str = field(repr=False)
    csrf_token: str = field(repr=False)


class AdminSecurityService:
    """Gère les sessions, le CSRF et la limitation des connexions."""

    def __init__(self, session: AsyncSession, settings: AdminSettings) -> None:
        self._session = session
        self._settings = settings
        self._password_hasher = PasswordHasher()

    async def issue_anonymous_session(self) -> IssuedAdminSession:
        return await self._issue_session(username=None, authenticated=False)

    async def login(
        self,
        *,
        current_token: str | None,
        csrf_token: str | None,
        username: str,
        password: str,
        ip_address: str,
        now: datetime | None = None,
    ) -> IssuedAdminSession | None:
        moment = now or datetime.now(UTC)
        normalized_username = username.strip()
        username_hash = self._digest(normalized_username.casefold())
        async with self._session.begin():
            current = await self._get_valid_session(current_token, moment=moment)
            if current is None or not self._csrf_matches(current, csrf_token):
                return None
            await self._lock_login_dimensions(ip_address, username_hash)
            cutoff = moment - timedelta(
                seconds=self._settings.admin_login_window_seconds
            )
            await self._session.execute(
                delete(AdminLoginAttempt).where(
                    AdminLoginAttempt.attempted_at < cutoff,
                    or_(
                        AdminLoginAttempt.ip_address == ip_address,
                        AdminLoginAttempt.username_hash == username_hash,
                    ),
                )
            )
            attempt_count = await self._session.scalar(
                select(func.count(AdminLoginAttempt.id)).where(
                    AdminLoginAttempt.attempted_at >= cutoff,
                    or_(
                        AdminLoginAttempt.ip_address == ip_address,
                        AdminLoginAttempt.username_hash == username_hash,
                    ),
                )
            )
            if (attempt_count or 0) >= self._settings.admin_login_max_attempts:
                return None

            username_valid = hmac.compare_digest(
                normalized_username.encode(),
                (self._settings.admin_username or "").encode(),
            )
            password_valid = self._verify_password(password)
            valid = username_valid and password_valid
            if not valid:
                self._session.add(
                    AdminLoginAttempt(
                        ip_address=ip_address,
                        username_hash=username_hash,
                        attempted_at=moment,
                    )
                )
                return None

            await self._session.delete(current)
            await self._session.execute(
                delete(AdminLoginAttempt).where(
                    or_(
                        AdminLoginAttempt.ip_address == ip_address,
                        AdminLoginAttempt.username_hash == username_hash,
                    )
                )
            )
        return await self._issue_session(
            username=normalized_username,
            authenticated=True,
            now=moment,
        )

    async def authenticate(
        self,
        token: str | None,
        csrf_token: str | None,
        *,
        now: datetime | None = None,
    ) -> AdminPrincipal | None:
        moment = now or datetime.now(UTC)
        async with self._session.begin():
            stored = await self._get_valid_session(token, moment=moment)
            if (
                stored is None
                or not stored.is_authenticated
                or stored.username is None
                or csrf_token is None
                or not self._csrf_matches(stored, csrf_token)
            ):
                return None
            return AdminPrincipal(
                username=stored.username,
                token_hash=stored.token_hash,
                csrf_token=csrf_token,
            )

    async def logout(self, token: str | None, csrf_token: str | None) -> bool:
        async with self._session.begin():
            stored = await self._get_valid_session(token)
            if stored is None or not self._csrf_matches(stored, csrf_token):
                return False
            await self._session.delete(stored)
            return True

    async def issue_form_token(self, principal: AdminPrincipal) -> str:
        token = secrets.token_urlsafe(32)
        async with self._session.begin():
            result = await self._session.execute(
                update(AdminSession)
                .where(AdminSession.token_hash == principal.token_hash)
                .values(form_token_hash=self._digest(token))
            )
            if result.rowcount != 1:
                raise RuntimeError("Session administrateur introuvable")
        return token

    async def consume_form_token(
        self, principal: AdminPrincipal, token: str | None
    ) -> bool:
        if token is None:
            return False
        async with self._session.begin():
            result = await self._session.execute(
                update(AdminSession)
                .where(
                    AdminSession.token_hash == principal.token_hash,
                    AdminSession.form_token_hash == self._digest(token),
                )
                .values(form_token_hash=None)
            )
            return result.rowcount == 1

    async def _issue_session(
        self,
        *,
        username: str | None,
        authenticated: bool,
        now: datetime | None = None,
    ) -> IssuedAdminSession:
        moment = now or datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        expires_at = moment + timedelta(
            seconds=self._settings.admin_session_ttl_seconds
        )
        async with self._session.begin():
            await self._session.execute(
                delete(AdminSession).where(AdminSession.expires_at <= moment)
            )
            self._session.add(
                AdminSession(
                    token_hash=self._digest(token),
                    csrf_hash=self._digest(csrf_token),
                    username=username,
                    is_authenticated=authenticated,
                    created_at=moment,
                    expires_at=expires_at,
                )
            )
        return IssuedAdminSession(token, csrf_token, expires_at)

    async def _get_valid_session(
        self, token: str | None, *, moment: datetime | None = None
    ) -> AdminSession | None:
        if token is None:
            return None
        stored = await self._session.get(AdminSession, self._digest(token))
        reference = moment or datetime.now(UTC)
        if stored is None or stored.expires_at <= reference:
            if stored is not None:
                await self._session.delete(stored)
            return None
        return stored

    def _csrf_matches(self, stored: AdminSession, csrf_token: str | None) -> bool:
        return csrf_token is not None and hmac.compare_digest(
            stored.csrf_hash, self._digest(csrf_token)
        )

    def _verify_password(self, password: str) -> bool:
        try:
            return self._password_hasher.verify(
                self._settings.admin_password_hash or "", password
            )
        except (InvalidHashError, VerifyMismatchError):
            return False

    async def _lock_login_dimensions(self, ip_address: str, username_hash: str) -> None:
        """Sérialise atomiquement les contrôles par IP et par identifiant."""
        lock_keys = sorted(
            {
                self._advisory_lock_key(f"ip:{ip_address}"),
                self._advisory_lock_key(f"username:{username_hash}"),
            }
        )
        statement = select(
            func.pg_advisory_xact_lock(bindparam("lock_key", type_=BigInteger))
        )
        for lock_key in lock_keys:
            await self._session.execute(statement, {"lock_key": lock_key})

    @staticmethod
    def _advisory_lock_key(value: str) -> int:
        digest = hashlib.sha256(value.encode()).digest()
        return int.from_bytes(digest[:8], byteorder="big", signed=True)

    def _digest(self, value: str) -> str:
        return hmac.new(
            (self._settings.admin_session_secret or "").encode(),
            value.encode(),
            hashlib.sha256,
        ).hexdigest()
