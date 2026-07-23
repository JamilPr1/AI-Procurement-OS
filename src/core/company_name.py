"""Resolve canonical buyer company names from messy website titles."""

from __future__ import annotations

import re
from typing import Any

GENERIC_KEYWORDS = (
    "promotional products", "custom gifts", "logo drinkware", "wholesale",
    "manufacturer", "factory", "oem", "odm", "buy online", "shop now",
    "official site", "home page", "welcome to", "leading supplier",
    "custom branded", "bulk order", "catalog", "drinkware",
)

SKIP_TITLE_WORDS = {"home", "homepage", "index", "welcome", "official website"}


def _is_seo_landing_title(text: str) -> bool:
    """Titles like 'Buy Custom Drinkware' — not real company names."""
    lower = (text or "").lower().strip()
    if re.match(r"^(buy|shop|get|order|custom)\s+", lower):
        return True
    if "custom" in lower and any(w in lower for w in ("drinkware", "gifts", "apparel", "bags", "products", "swag")):
        return len(lower.split()) <= 6
    return False


def business_name_from_email(email: str) -> str:
    """Derive a display business name from a corporate email address."""
    return _name_from_email(email)


def _clean(part: str) -> str:
    return re.sub(r"\s+", " ", (part or "").strip(" ·-|–—"))


def _title_looks_generic(text: str) -> bool:
    lower = text.lower()
    if "·" in text and len(text) > 28:
        return True
    hits = sum(1 for kw in GENERIC_KEYWORDS if kw in lower)
    if hits >= 2:
        return True
    if hits >= 1 and len(text) > 32:
        return True
    if lower in SKIP_TITLE_WORDS:
        return True
    return False


def _name_from_domain(domain: str) -> str:
    base = (domain or "").lower().replace("www.", "").split(".")[0]
    if not base:
        return ""
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)
    spaced = re.sub(r"[-_]+", " ", spaced)
    words = [w for w in spaced.split() if w]
    if not words:
        return base.title()
    return " ".join(w.capitalize() for w in words)


def _name_from_email(email: str) -> str:
    if not email or "@" not in email:
        return ""
    domain = email.split("@", 1)[1].lower()
    skip = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com"}
    if domain in skip:
        return ""
    return _name_from_domain(domain)


def resolve_company_name(
    *,
    title: str = "",
    domain: str = "",
    email: str = "",
    website: str = "",
) -> str:
    """Pick the real business name, not SEO page titles."""
    email_name = _name_from_email(email)
    raw_title = _clean(title)

    if email_name and (not raw_title or _title_looks_generic(raw_title) or _is_seo_landing_title(raw_title)):
        return email_name[:80]

    parts = [_clean(p) for p in re.split(r"[\|–—]", raw_title) if _clean(p)]

    candidates: list[str] = []
    if len(parts) >= 2:
        if _title_looks_generic(parts[0]) and not _title_looks_generic(parts[-1]):
            candidates.append(parts[-1])
        elif not _title_looks_generic(parts[0]):
            candidates.append(parts[0])
        else:
            candidates.extend(reversed(parts))
    elif parts:
        if not _title_looks_generic(parts[0]):
            candidates.append(parts[0])
        elif len(parts[0]) < 40:
            candidates.append(parts[0])

    for c in candidates:
        if c and not _title_looks_generic(c) and c.lower() not in SKIP_TITLE_WORDS:
            return c[:80]

    for c in candidates:
        if c and c.lower() not in SKIP_TITLE_WORDS:
            return c[:80]

    for src in (_name_from_domain(domain), _name_from_email(email)):
        if src and not _title_looks_generic(src):
            return src[:80]

  # Last resort: shortest non-generic title segment
    for p in reversed(parts):
        if p and len(p) < 50:
            return p[:80]

    return _name_from_domain(domain) or "Unknown Company"


def normalize_lead_record(lead: dict[str, Any]) -> dict[str, Any]:
    """Ensure lead dict uses a proper company_name (prefer email domain over SEO titles)."""
    if not lead:
        return lead
    email = lead.get("email") or (lead.get("data") or {}).get("email", "")
    resolved = resolve_company_name(
        title=lead.get("website_title") or lead.get("company_name", ""),
        domain=lead.get("domain", ""),
        email=email,
        website=lead.get("website", ""),
    )
    if resolved and resolved != "Unknown Company":
        lead = {**lead, "company_name": resolved, "email": email or lead.get("email", "")}
    return lead
