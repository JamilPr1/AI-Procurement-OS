"""Session tokens for CRM API access."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse

TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days

PUBLIC_API_PATHS = {
    ("POST", "/api/auth/login"),
    ("GET", "/api/health"),
    ("GET", "/api/contact"),
    ("POST", "/api/demo-request"),
}


def _secret() -> bytes:
    key = os.getenv("SESSION_SECRET", "").strip() or os.getenv("PORTAL_SIGNING_SECRET", "").strip()
    if not key:
        key = "dev-only-change-SESSION_SECRET-in-production"
    return key.encode()


def issue_token(user: dict[str, Any]) -> str:
    payload = {
        "email": user.get("email"),
        "role": user.get("role"),
        "tenant_id": user.get("tenant_id"),
        "tenant_slug": user.get("tenant_slug"),
        "name": user.get("name"),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    sig = hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def verify_token(token: str) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    raw, sig = token.rsplit(".", 1)
    expected = hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
    except (json.JSONDecodeError, ValueError):
        return None
    if int(payload.get("exp") or 0) < int(time.time()):
        return None
    return payload


def _is_public_api(method: str, path: str) -> bool:
    if (method, path) in PUBLIC_API_PATHS:
        return True
    if path.startswith("/api/store/") or path.startswith("/api/portal/"):
        return True
    if method == "GET" and path == "/api/saas/tenants":
        return True
    return False


def get_request_user(request: Request) -> dict[str, Any] | None:
    return getattr(request.state, "user", None)


def require_user(request: Request) -> dict[str, Any]:
    user = get_request_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_superadmin(request: Request) -> dict[str, Any]:
    user = require_user(request)
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


async def auth_middleware(request: Request, call_next):  # noqa: ANN001
    path = request.url.path
    if path.startswith("/api/") and not _is_public_api(request.method, path):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        user = verify_token(auth[7:].strip())
        if not user:
            return JSONResponse(
                {"detail": "Invalid or expired session — please sign in again"},
                status_code=401,
            )
        request.state.user = user
        if path.startswith("/api/admin/") and user.get("role") != "superadmin":
            return JSONResponse({"detail": "Super admin access required"}, status_code=403)
    return await call_next(request)
