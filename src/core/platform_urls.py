"""Resolve public URLs for emails, portals, and credentials."""

from __future__ import annotations

import os
from typing import Any


def get_public_base_url(config: dict[str, Any] | None = None) -> str:
    """Return the public base URL (no trailing slash)."""
    for key in ("RENDER_EXTERNAL_URL", "PUBLIC_URL", "APP_URL"):
        url = os.getenv(key, "").strip().rstrip("/")
        if url:
            return url

    if not config:
        return "http://127.0.0.1:8765"

    dash = config.get("dashboard", {})
    host = dash.get("host", "127.0.0.1")
    port = int(dash.get("port", 8765))
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"

    scheme = "https" if os.getenv("RENDER") else "http"
    if (scheme == "https" and port == 443) or (scheme == "http" and port == 80):
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"
