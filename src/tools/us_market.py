"""US-market filters for lead discovery."""

from __future__ import annotations

import re

NON_US_TLDS = (
    ".co.uk", ".uk", ".cn", ".com.cn", ".de", ".fr", ".in", ".au", ".ca",
    ".ru", ".jp", ".kr", ".it", ".es", ".br", ".mx", ".nl", ".pl", ".tw",
    ".hk", ".sg", ".my", ".vn", ".th", ".id", ".ph", ".pk", ".bd",
)

NON_US_TEXT_SIGNALS = (
    "united kingdom", " u.k.", " uk-based", "shanghai", "guangdong", "shenzhen",
    "dongguan", "yiwu", "ningbo", "guangzhou", "made in china", "india-based",
    "toronto, on", "vancouver, bc", "montreal, qc", "europe only", "eu only",
    "australia", "new zealand", "mexico city", "são paulo",
    "zhejiang", "fujian", "jiangsu", "anhui", "henan", "hubei", "hunan",
    "province, china", ", china", " china.", "hong kong", "taiwan",
    "oem factory", "odm factory", "factory in china", "china factory",
    "export from china", "shenzhen factory", "guangdong province",
)

CHINA_EMAIL_DOMAINS = (
    "qq.com", "163.com", "126.com", "sina.com", "sohu.com", "aliyun.com",
    "foxmail.com", "139.com", "yeah.net", "21cn.com",
)

US_TEXT_SIGNALS = (
    "united states", " usa", " u.s.", " u.s.a", "american", "north america",
    "texas", "california", "new york", "florida", "illinois", "ohio", "georgia",
    "pennsylvania", "michigan", "north carolina", "virginia", "washington, dc",
    "los angeles", "chicago", "houston", "phoenix", "dallas", "san diego",
    "atlanta", "boston", "seattle", "denver", "miami", "nashville",
    "minnesota", "wisconsin", "colorado", "arizona", "new jersey",
    "connecticut", "maryland", "massachusetts", "oregon", "tennessee",
)

# Strict NANP — area/exchange cannot start with 0 or 1
US_PHONE_RE = re.compile(
    r"(?:\+1[\s.-]?|1[\s.-])"
    r"\(?[2-9]\d{2}\)?[\s.-]?[2-9]\d{2}[\s.-]?\d{4}"
    r"|"
    r"(?<!\d)\(?[2-9]\d{2}\)?[\s.-][2-9]\d{2}[\s.-]\d{4}(?!\d)"
)

FOREIGN_PHONE_RE = re.compile(
    r"\+(?:86|44|91|61|49|33|81|82|55|52|39|34|7|852|886)\b"
)

CHINA_DOMAIN_HINTS = (
    "china", "chinese", "shenzhen", "guangzhou", "yiwu", "alibaba",
    "1688", "made-in-china", "globalsources",
)

SUPPLIER_NOT_BUYER_SIGNALS = (
    "oem manufacturer", "odm manufacturer", "we are a factory", "our factory",
    "factory in", "manufacturing factory", "export company", "trading company china",
    "custom manufacturer", "drinkware manufacturer", "products manufacturer",
)


def is_us_domain(domain: str) -> bool:
    d = (domain or "").lower().strip()
    if not d:
        return False
    if any(h in d for h in CHINA_DOMAIN_HINTS):
        return False
    if d.endswith(".us"):
        return True
    if any(d.endswith(t) for t in NON_US_TLDS):
        return False
    return True


def has_foreign_phone(text: str, phones: list[str] | None = None) -> bool:
    blob = text or ""
    if FOREIGN_PHONE_RE.search(blob):
        return True
    for raw in phones or []:
        p = str(raw).strip()
        if FOREIGN_PHONE_RE.search(p):
            return True
        if p.startswith("86") and len(re.sub(r"\D", "", p)) >= 11:
            return True
    return False


def has_us_phone(phones: list[str] | None, text: str = "") -> bool:
    blob = f"{text} {' '.join(phones or [])}"
    return bool(US_PHONE_RE.search(blob))


def has_china_email(emails: list[str] | None) -> bool:
    for email in emails or []:
        domain = email.lower().split("@")[-1]
        if domain in CHINA_EMAIL_DOMAINS or domain.endswith(".cn"):
            return True
    return False


def is_supplier_not_buyer(text: str) -> bool:
    blob = (text or "").lower()
    if any(sig in blob for sig in SUPPLIER_NOT_BUYER_SIGNALS):
        return True
    if "manufacturer" in blob and not any(
        b in blob for b in ("distributor", "buyer", "retailer", "reseller", "catalog")
    ):
        return True
    return False


def is_us_market(
    *,
    domain: str = "",
    text: str = "",
    phones: list[str] | None = None,
    emails: list[str] | None = None,
    strict: bool = True,
) -> bool:
    """Return True if lead appears to be a US-based buyer."""
    blob = (text or "").lower()
    d = (domain or "").lower()

    if not is_us_domain(d):
        return False
    if any(sig in blob for sig in NON_US_TEXT_SIGNALS):
        return False
    if has_foreign_phone(blob, phones):
        return False
    if has_china_email(emails):
        return False
    if is_supplier_not_buyer(blob):
        return False

    if has_us_phone(phones, blob):
        return True
    if d.endswith(".us"):
        return True
    if any(sig in blob for sig in US_TEXT_SIGNALS):
        return True
    if " usa" in blob or blob.endswith(" usa") or "united states" in blob:
        return True

    if not strict:
        return False

    return False
