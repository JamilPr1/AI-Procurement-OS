"""Deduplication keys — brain-aligned entity matching."""

from __future__ import annotations

import re
from urllib.parse import urlparse


def normalize_domain(url_or_domain: str) -> str:
    if not url_or_domain:
        return ""
    s = url_or_domain.strip().lower()
    if "://" in s:
        s = urlparse(s).netloc
    return s.replace("www.", "").split("/")[0]


def lead_dedupe_key(data: dict) -> str:
    domain = normalize_domain(data.get("domain") or data.get("website", ""))
    if domain:
        return f"domain:{domain}"
    email = (data.get("email") or "").strip().lower()
    if email:
        return f"email:{email}"
    name = re.sub(r"[^a-z0-9]", "", (data.get("company_name") or "").lower())
    return f"name:{name}" if name else ""


def supplier_dedupe_key(data: dict) -> str:
    url = (data.get("url") or "").strip().lower()
    if url:
        path = urlparse(url).path.strip("/")[:60]
        domain = normalize_domain(url)
        if path:
            return f"url:{domain}/{path}"
        return f"domain:{domain}"
    name = re.sub(r"[^a-z0-9]", "", (data.get("factory_name") or "").lower())[:80]
    return f"name:{name}" if name else ""


def deal_dedupe_key(lead_id: str, stage: str = "") -> str:
    return f"lead:{lead_id}:{stage or 'active'}"
