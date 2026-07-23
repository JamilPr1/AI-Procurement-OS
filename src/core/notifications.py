"""Admin notifications — demo requests, alerts, and team email routing."""

from __future__ import annotations

import logging
import os
from typing import Any

from src.core.email import EmailService

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_EMAIL = "aarfa.developers@gmail.com"


def admin_email() -> str:
    return (
        os.getenv("CONTACT_EMAIL", "").strip()
        or os.getenv("NOTIFY_EMAIL", "").strip()
        or DEFAULT_ADMIN_EMAIL
    )


def _send_resend(to: str, subject: str, body: str, *, html: str | None = None) -> dict[str, Any] | None:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        return None
    import httpx

    from_addr = os.getenv("RESEND_FROM", "").strip() or f"AI Procurement OS <onboarding@resend.dev>"
    payload: dict[str, Any] = {
        "from": from_addr,
        "to": [to],
        "subject": subject,
        "text": body,
    }
    if html:
        payload["html"] = html
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
        r.raise_for_status()
        return {"status": "sent", "provider": "resend", "to": to, "subject": subject, "id": r.json().get("id")}
    except Exception as e:
        logger.warning("Resend notification failed: %s", e)
        return {"status": "error", "provider": "resend", "error": str(e)}


def _send_smtp_force(to: str, subject: str, body: str, *, html: str | None = None) -> dict[str, Any] | None:
    """Send via SMTP even when EMAIL_DRY_RUN is set (admin notifications only)."""
    svc = EmailService()
    if not svc.is_configured():
        return None
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = svc.from_email
    msg["To"] = to
    msg.attach(MIMEText(body, "plain", "utf-8"))
    if html:
        msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP(svc.smtp_host, svc.smtp_port, timeout=30) as server:
            server.starttls()
            server.login(svc.smtp_user, svc.smtp_pass)
            server.sendmail(svc.from_email, [to], msg.as_string())
        return {"status": "sent", "provider": "smtp", "to": to, "subject": subject}
    except Exception as e:
        logger.warning("SMTP notification failed: %s", e)
        return {"status": "error", "provider": "smtp", "error": str(e)}


def notify_admin(subject: str, body: str, *, html: str | None = None) -> dict[str, Any]:
    """Deliver a notification to the admin inbox (Resend → SMTP → log)."""
    to = admin_email()
    result = _send_resend(to, subject, body, html=html)
    if result and result.get("status") == "sent":
        logger.info("Admin notification sent via Resend to %s", to)
        return result
    result = _send_smtp_force(to, subject, body, html=html)
    if result and result.get("status") == "sent":
        logger.info("Admin notification sent via SMTP to %s", to)
        return result
    logger.info("Admin notification logged (no mail provider): %s — %s", to, subject)
    return {
        "status": "logged",
        "to": to,
        "subject": subject,
        "message": "Saved locally — configure RESEND_API_KEY or SMTP_* on Render to receive email",
    }


def notify_demo_request(entry: dict[str, Any]) -> dict[str, Any]:
    name = entry.get("name", "")
    email = entry.get("email", "")
    company = entry.get("company", "")
    message = entry.get("message", "") or "(none)"
    source = entry.get("source", "landing")
    created = entry.get("created_at", "")

    subject = f"New pilot request — {company}"
    body = (
        f"New demo/pilot request on AI Procurement OS\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Company: {company}\n"
        f"Source: {source}\n"
        f"Submitted: {created}\n"
        f"What they source: {message}\n"
    )
    html = (
        f"<h2>New pilot request</h2>"
        f"<p><b>Name:</b> {name}<br/>"
        f"<b>Email:</b> <a href='mailto:{email}'>{email}</a><br/>"
        f"<b>Company:</b> {company}<br/>"
        f"<b>Source:</b> {source}<br/>"
        f"<b>Submitted:</b> {created}</p>"
        f"<p><b>What they source:</b> {message}</p>"
    )
    return notify_admin(subject, body, html=html)
