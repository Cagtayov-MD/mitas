"""MITAS local access gate shared by API services."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time
from typing import Any

from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware


ACCESS_USERNAME = "mitas"
PW_ID_SUFFIX = "_61"
ACCESS_COOKIE_NAME = "mitas_access"
ACCESS_TTL_SECONDS = 12 * 60 * 60
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SECRET_PATH = PROJECT_ROOT / "config" / ".mitas_access_secret"


def is_valid_access_credentials(username: str, pw_id: str) -> bool:
    normalized_username = username.strip().lower()
    normalized_pw_id = pw_id.strip()
    return (
        normalized_username == ACCESS_USERNAME
        and len(normalized_pw_id) > len(PW_ID_SUFFIX)
        and normalized_pw_id.endswith(PW_ID_SUFFIX)
    )


def add_mitas_access_gate(app: Any) -> None:
    app.include_router(create_access_router())
    app.add_middleware(MitasAccessMiddleware)


def create_access_router() -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    @router.get("/session")
    async def session(request: Request) -> dict[str, Any]:
        return {
            "authenticated": is_request_authorized(request),
            "username": ACCESS_USERNAME if is_request_authorized(request) else None,
        }

    @router.post("/login")
    async def login(request: Request) -> Response:
        try:
            payload = await request.json()
        except Exception:  # noqa: BLE001
            payload = {}
        username = str(payload.get("username") or "")
        pw_id = str(payload.get("pwId") or payload.get("pw_id") or payload.get("password") or "")
        if not is_valid_access_credentials(username, pw_id):
            return JSONResponse({"detail": "Giriş reddedildi."}, status_code=401)

        response = JSONResponse({"authenticated": True, "username": ACCESS_USERNAME})
        response.set_cookie(
            ACCESS_COOKIE_NAME,
            create_access_token(ACCESS_USERNAME),
            httponly=True,
            secure=_cookie_secure(),
            samesite="lax",
            max_age=ACCESS_TTL_SECONDS,
            path="/",
        )
        return response

    @router.post("/logout")
    async def logout() -> Response:
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
        return response

    return router


class MitasAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if _is_exempt_request(request):
            return await call_next(request)
        if not is_request_authorized(request):
            return JSONResponse({"detail": "MITAS girişi gerekli."}, status_code=401)
        return await call_next(request)


def is_request_authorized(request: Request) -> bool:
    return validate_access_token(_access_token_from_request(request)) is not None


def is_websocket_authorized(websocket: WebSocket) -> bool:
    token = websocket.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        authorization = websocket.headers.get("authorization", "")
        token = _bearer_token(authorization)
    return validate_access_token(token) is not None


def access_cookie_header_from_request(request: Request) -> str:
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    return f"{ACCESS_COOKIE_NAME}={token}" if token else ""


def create_access_token(username: str) -> str:
    now = int(time.time())
    payload = {
        "u": username,
        "iat": now,
        "exp": now + ACCESS_TTL_SECONDS,
        "n": secrets.token_urlsafe(12),
        "v": 1,
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))
    signature = _sign(body)
    return f"{body}.{signature}"


def validate_access_token(token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    body, signature = token.split(".", 1)
    expected = _sign(body)
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_b64decode(body).decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if payload.get("u") != ACCESS_USERNAME:
        return None
    try:
        expires_at = int(payload.get("exp") or 0)
    except (TypeError, ValueError):
        return None
    if expires_at < int(time.time()):
        return None
    return payload


def _is_exempt_request(request: Request) -> bool:
    if request.method.upper() == "OPTIONS":
        return True
    path = request.url.path
    return path.startswith("/api/auth/")


def _access_token_from_request(request: Request) -> str | None:
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if token:
        return token
    return _bearer_token(request.headers.get("authorization", ""))


def _bearer_token(value: str) -> str | None:
    prefix = "bearer "
    if value.lower().startswith(prefix):
        return value[len(prefix):].strip()
    return None


def _sign(body: str) -> str:
    signature = hmac.new(_access_secret(), body.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(signature)


def _access_secret() -> bytes:
    configured = os.environ.get("MITAS_ACCESS_SECRET", "").strip()
    if configured:
        return configured.encode("utf-8")

    path = Path(os.environ.get("MITAS_ACCESS_SECRET_FILE", "") or DEFAULT_SECRET_PATH)
    try:
        if path.exists():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value.encode("utf-8")
        value = secrets.token_urlsafe(48)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value + "\n", encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return value.encode("utf-8")
    except OSError:
        fallback = f"mitas-local-fallback:{PROJECT_ROOT}"
        return fallback.encode("utf-8")


def _cookie_secure() -> bool:
    return os.environ.get("MITAS_ACCESS_COOKIE_SECURE", "").strip().lower() in {"1", "true", "yes", "on"}


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
