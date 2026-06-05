"""User-scoped Tedial session broker.

The broker deliberately avoids username/password handling. A login proxy or
WebView adapter will feed Set-Cookie headers into this layer after the user logs
in with Tedial. The API/proxy layer then asks for a connected user session and
uses the cookie header for Tedial AJAX calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import secrets
from threading import RLock
from typing import Iterable


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TedialSessionStatus(str, Enum):
    disconnected = "disconnected"
    connecting = "connecting"
    connected = "connected"
    expired = "expired"
    error = "error"


class TedialSessionError(RuntimeError):
    """Base error for Tedial session broker failures."""


class TedialSessionNotConnected(TedialSessionError):
    """Raised when an operation requires a connected Tedial session."""


@dataclass
class TedialCookieJar:
    """Small cookie jar abstraction that never exposes values via repr."""

    _cookies: dict[str, str] = field(default_factory=dict)

    def update_from_set_cookie_headers(self, headers: Iterable[str]) -> None:
        for header in headers:
            parsed = SimpleCookie()
            parsed.load(header)
            for name, morsel in parsed.items():
                self._cookies[name] = morsel.value

    def update_cookie_header(self, cookie_header: str) -> None:
        if not cookie_header:
            return
        for part in cookie_header.split(";"):
            if "=" not in part:
                continue
            name, value = part.strip().split("=", 1)
            if name:
                self._cookies[name] = value

    def as_header(self) -> str:
        return "; ".join(f"{name}={value}" for name, value in sorted(self._cookies.items()))

    def names(self) -> list[str]:
        return sorted(self._cookies)

    def clear(self) -> None:
        self._cookies.clear()

    def to_dict(self) -> dict[str, str]:
        return dict(self._cookies)

    def update_from_mapping(self, cookies: dict[str, str]) -> None:
        for name, value in cookies.items():
            if name:
                self._cookies[str(name)] = str(value)

    def __len__(self) -> int:
        return len(self._cookies)

    def __bool__(self) -> bool:
        return bool(self._cookies)

    def __repr__(self) -> str:
        return f"TedialCookieJar(names={self.names()!r}, values=<MASKED>)"


@dataclass(frozen=True)
class TedialSessionSnapshot:
    user_id: str
    session_id: str
    status: TedialSessionStatus
    remember: bool
    cookie_names: tuple[str, ...]
    created_at: datetime
    updated_at: datetime
    connected_at: datetime | None = None
    last_checked_at: datetime | None = None
    expires_at: datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "remember": self.remember,
            "cookie_names": list(self.cookie_names),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "error": self.error,
        }


@dataclass
class TedialUserSession:
    user_id: str
    session_id: str = field(default_factory=lambda: secrets.token_urlsafe(18))
    status: TedialSessionStatus = TedialSessionStatus.disconnected
    remember: bool = False
    cookies: TedialCookieJar = field(default_factory=TedialCookieJar)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    connected_at: datetime | None = None
    last_checked_at: datetime | None = None
    expires_at: datetime | None = None
    error: str | None = None

    def snapshot(self) -> TedialSessionSnapshot:
        return TedialSessionSnapshot(
            user_id=self.user_id,
            session_id=self.session_id,
            status=self.status,
            remember=self.remember,
            cookie_names=tuple(self.cookies.names()),
            created_at=self.created_at,
            updated_at=self.updated_at,
            connected_at=self.connected_at,
            last_checked_at=self.last_checked_at,
            expires_at=self.expires_at,
            error=self.error,
        )


class TedialSessionBroker:
    """In-memory user session registry for the Phase 1 POC."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self._lock = RLock()
        self._sessions: dict[str, TedialUserSession] = {}
        self._storage_dir = Path(storage_dir) if storage_dir else _default_storage_dir()

    def start(self, user_id: str, remember: bool = False) -> TedialSessionSnapshot:
        with self._lock:
            session = self._session_for(user_id)
            # Never trust a remembered cookie's *presence* as proof of liveness.
            # A persisted (but expired) JSESSIONID would otherwise flip the
            # session straight to `connected`, and login_proxy's
            # `_should_return_to_poc_ui` gate (status == "connected") would
            # bounce the login iframe back to /tedial without ever showing the
            # Tedial login form — the "Bağlan + bayat cookie" bug. Always start
            # in `connecting`; the login proxy / health check decides if the
            # remembered cookie still authenticates (valid cookie => the default
            # page load marks connected and redirects seamlessly; stale cookie
            # => Tedial returns the login form, which now renders in the iframe).
            session.status = TedialSessionStatus.connecting
            session.remember = remember
            session.updated_at = utc_now()
            session.error = None
            self._persist_or_delete(session)
            return session.snapshot()

    def attach_set_cookie_headers(
        self,
        user_id: str,
        headers: Iterable[str],
        remember: bool | None = None,
        mark_connected: bool = True,
    ) -> TedialSessionSnapshot:
        with self._lock:
            session = self._session_for(user_id)
            session.cookies.update_from_set_cookie_headers(headers)
            if remember is not None:
                session.remember = remember
            if session.cookies and mark_connected:
                session.status = TedialSessionStatus.connected
                session.connected_at = utc_now()
                session.error = None
            elif session.cookies:
                if session.status == TedialSessionStatus.disconnected:
                    session.status = TedialSessionStatus.connecting
                session.error = None
            else:
                session.status = TedialSessionStatus.error
                session.error = "No Tedial cookies were captured"
            session.updated_at = utc_now()
            self._persist_or_delete(session)
            return session.snapshot()

    def attach_cookie_header(
        self,
        user_id: str,
        cookie_header: str,
        remember: bool | None = None,
    ) -> TedialSessionSnapshot:
        with self._lock:
            session = self._session_for(user_id)
            session.cookies.update_cookie_header(cookie_header)
            if remember is not None:
                session.remember = remember
            if session.cookies:
                session.status = TedialSessionStatus.connected
                session.connected_at = utc_now()
                session.error = None
            else:
                session.status = TedialSessionStatus.error
                session.error = "Empty Tedial cookie header"
            session.updated_at = utc_now()
            self._persist_or_delete(session)
            return session.snapshot()

    def get(self, user_id: str) -> TedialSessionSnapshot:
        with self._lock:
            session = self._session_for(user_id)
            return session.snapshot()

    def cookie_header_for(self, user_id: str) -> str:
        with self._lock:
            session = self._session_for(user_id)
            if session is None or session.status != TedialSessionStatus.connected or not session.cookies:
                raise TedialSessionNotConnected(f"Tedial session is not connected for user: {user_id}")
            return session.cookies.as_header()

    def cookie_header_if_any(self, user_id: str) -> str:
        """Return captured cookies regardless of health status.

        Login proxy requests need to forward cookies while the session is still
        in `connecting` state. API calls should continue using `cookie_header_for`.
        """
        with self._lock:
            session = self._session_for(user_id)
            if session is None or not session.cookies:
                return ""
            return session.cookies.as_header()

    def mark_checked(self, user_id: str, connected: bool, error: str | None = None) -> TedialSessionSnapshot:
        with self._lock:
            session = self._session_for(user_id)
            session.last_checked_at = utc_now()
            session.updated_at = session.last_checked_at
            session.status = TedialSessionStatus.connected if connected else TedialSessionStatus.expired
            session.error = None if connected else error or "Tedial session expired"
            self._persist_or_delete(session)
            return session.snapshot()

    def forget(self, user_id: str) -> TedialSessionSnapshot:
        with self._lock:
            session = self._session_for(user_id)
            session.cookies.clear()
            session.status = TedialSessionStatus.disconnected
            session.remember = False
            session.connected_at = None
            session.expires_at = None
            session.updated_at = utc_now()
            session.error = None
            self._delete_persisted(user_id)
            return session.snapshot()

    def list_snapshots(self) -> list[TedialSessionSnapshot]:
        with self._lock:
            return [session.snapshot() for session in self._sessions.values()]

    def _session_for(self, user_id: str) -> TedialUserSession:
        session = self._sessions.get(user_id)
        if session is not None:
            return session
        session = self._load_persisted(user_id) or TedialUserSession(user_id=user_id)
        self._sessions[user_id] = session
        return session

    def _persist_or_delete(self, session: TedialUserSession) -> None:
        # Keep a remembered cookie jar on disk for the active session lifecycle
        # (connected OR connecting). `start()` now lands in `connecting` until the
        # login proxy confirms liveness, so persisting on `connecting` keeps the
        # remembered cookie durable across a server restart. Dead states
        # (expired/disconnected/error) still purge — note mark_checked(False)
        # sets `expired`, so the expire-purge contract is unchanged.
        keepable_statuses = (TedialSessionStatus.connected, TedialSessionStatus.connecting)
        if session.remember and session.cookies and session.status in keepable_statuses:
            self._storage_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "user_id": session.user_id,
                "session_id": session.session_id,
                "remember": session.remember,
                "cookies": session.cookies.to_dict(),
                "created_at": session.created_at.isoformat(),
                "connected_at": session.connected_at.isoformat() if session.connected_at else None,
                "updated_at": session.updated_at.isoformat(),
            }
            self._storage_path(session.user_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            self._delete_persisted(session.user_id)

    def _load_persisted(self, user_id: str) -> TedialUserSession | None:
        path = self._storage_path(user_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            cookies = payload.get("cookies") or {}
            if not isinstance(cookies, dict) or not cookies:
                return None
            session = TedialUserSession(user_id=user_id, session_id=str(payload.get("session_id") or secrets.token_urlsafe(18)))
            session.remember = True
            session.cookies.update_from_mapping({str(name): str(value) for name, value in cookies.items()})
            session.status = TedialSessionStatus.connected
            session.connected_at = _parse_datetime(payload.get("connected_at")) or utc_now()
            session.updated_at = utc_now()
            return session
        except Exception:
            return None

    def _delete_persisted(self, user_id: str) -> None:
        path = self._storage_path(user_id)
        if path.exists():
            path.unlink()

    def _storage_path(self, user_id: str) -> Path:
        return self._storage_dir / f"{_safe_user_id(user_id)}.cookies"


def _default_storage_dir() -> Path:
    configured = os.environ.get("MITAS_TEDIAL_SESSION_DIR", "").strip()
    return Path(configured) if configured else Path(".tedial_sessions")


def _safe_user_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe.strip("._-") or "dev-local"


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
