"""Extract contact channels from entity data."""

from __future__ import annotations

import re
from typing import Any


WHATSAPP_RE = re.compile(r"(?:wa\.me/|whatsapp\.com/send\?phone=|whatsapp:)\+?(\d{8,15})", re.I)
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
JUNK_EMAIL_RE = re.compile(
    r"@sentry\.|noreply|no-reply|donotreply|mailer-daemon|@example\.|@test\.|notifications?@",
    re.I,
)


def is_usable_buyer_email(email: str) -> bool:
    e = (email or "").strip()
    return bool(e) and not JUNK_EMAIL_RE.search(e)


def is_plausible_buyer_phone(phone: str) -> bool:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) < 10 or len(digits) > 15:
        return False
    # Reject obvious non-phone numeric IDs from page markup
    if len(set(digits)) <= 2:
        return False
    return True


def extract_buyer_contacts(data: dict[str, Any]) -> dict[str, Any]:
    """Buyer contacts — only explicit lead fields, never scraped page noise."""
    raw_email = (data.get("email") or "").strip()
    email_is_junk = bool(raw_email) and not is_usable_buyer_email(raw_email)

    emails: list[str] = []
    if raw_email and not email_is_junk:
        emails.append(raw_email)
    phones: list[str] = []
    # Skip phone when email is junk — phone was usually scraped from the same page
    if data.get("phone") and not email_is_junk:
        p = str(data["phone"]).strip()
        if is_plausible_buyer_phone(p) and p not in phones:
            phones.append(p)
    website = (data.get("website") or "").strip()
    return {
        "emails": emails,
        "phones": phones,
        "whatsapp": [],
        "website": website,
        "primary_email": emails[0] if emails else "",
        "primary_phone": phones[0] if phones else "",
        "primary_whatsapp": None,
        "contact_note": _buyer_contact_note(emails, phones, website, raw_email),
    }


def _buyer_contact_note(emails: list[str], phones: list[str], website: str, raw_email: str) -> str:
    if emails or phones:
        return ""
    if raw_email and not is_usable_buyer_email(raw_email):
        return "Only a monitoring/placeholder email was found on their site — use the website contact form."
    if website:
        return "No direct buyer email on file — use the website contact form."
    return "No buyer contact on file — add details on the Leads page."


def extract_contacts(data: dict[str, Any]) -> dict[str, Any]:
    """Pull emails, phones, WhatsApp from supplier/lead data and snippets."""
    text = " ".join(str(v) for v in [
        data.get("url", ""),
        data.get("search_snippet", ""),
        data.get("website_text_preview", ""),
        data.get("meta_description", ""),
    ])
    emails = list(dict.fromkeys(data.get("emails_found") or []))
    if data.get("email") and data["email"] not in emails:
        emails.insert(0, data["email"])
    for m in EMAIL_RE.findall(text):
        if m.lower() not in [e.lower() for e in emails]:
            emails.append(m)

    phones = list(dict.fromkeys(data.get("phones_found") or []))
    if data.get("phone") and data["phone"] not in phones:
        phones.insert(0, data["phone"])

    whatsapp: list[dict[str, str]] = []
    for m in WHATSAPP_RE.findall(text):
        num = re.sub(r"\D", "", m)
        if num:
            whatsapp.append({"number": f"+{num}", "link": f"https://wa.me/{num}"})
    url = data.get("url", "")
    if "wa.me" in url.lower():
        m = WHATSAPP_RE.search(url)
        if m:
            num = re.sub(r"\D", "", m.group(1))
            entry = {"number": f"+{num}", "link": f"https://wa.me/{num}"}
            if entry not in whatsapp:
                whatsapp.append(entry)

    # Chinese mobile patterns in snippets (common on MIC/Alibaba)
    for m in re.finditer(r"(?:whatsapp|wechat|微信)[:\s]*(\+?\d{10,15})", text, re.I):
        num = re.sub(r"\D", "", m.group(1))
        entry = {"number": f"+{num}", "link": f"https://wa.me/{num}"}
        if entry not in whatsapp:
            whatsapp.append(entry)

    return {
        "emails": emails[:5],
        "phones": phones[:5],
        "whatsapp": whatsapp[:3],
        "primary_email": emails[0] if emails else "",
        "primary_phone": phones[0] if phones else "",
        "primary_whatsapp": whatsapp[0] if whatsapp else None,
    }


def alibaba_contact_url(supplier_url: str) -> str | None:
    """Build Alibaba contact/message URL if possible."""
    if not supplier_url or "alibaba.com" not in supplier_url.lower():
        return None
    if "/company_profile.html" in supplier_url or ".en.alibaba.com" in supplier_url:
        return supplier_url
    return supplier_url
