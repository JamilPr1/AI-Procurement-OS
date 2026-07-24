"""Email delivery — SMTP with dry-run when not configured."""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any


class EmailService:
    def __init__(self) -> None:
        self.smtp_host = os.getenv("SMTP_HOST", "").strip()
        self.smtp_port = int(os.getenv("SMTP_PORT", "587") or "587")
        self.smtp_user = os.getenv("SMTP_USER", "").strip()
        self.smtp_pass = os.getenv("SMTP_PASS", "").strip()
        self.from_email = os.getenv("SMTP_FROM", self.smtp_user).strip() or self.smtp_user
        configured = self.is_configured()
        default_dry = "true" if not configured else "false"
        self.dry_run = os.getenv("EMAIL_DRY_RUN", default_dry).lower() in ("1", "true", "yes")

    def is_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_pass)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "dry_run": self.dry_run,
            "from_email": self.from_email or None,
            "host": self.smtp_host or None,
        }

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        *,
        cc: str | None = None,
        html: bool = False,
        html_body: str | None = None,
    ) -> dict[str, Any]:
        to = (to or "").strip()
        if not to:
            raise ValueError("Recipient email is required")

        if self.dry_run or not self.is_configured():
            return {
                "status": "dry_run",
                "to": to,
                "subject": subject,
                "body_preview": body[:500],
                "html_preview": (html_body or "")[:500] if html_body else None,
                "message": "Demo email recorded — view full flow on Contacts page (SMTP not configured)",
            }

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = to
        if cc:
            msg["Cc"] = cc
        msg.attach(MIMEText(body, "plain", "utf-8"))
        if html_body or html:
            msg.attach(MIMEText(html_body or body, "html", "utf-8"))

        recipients = [to]
        if cc:
            recipients.append(cc)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.from_email, recipients, msg.as_string())
        except Exception as e:
            return {
                "status": "dry_run",
                "to": to,
                "subject": subject,
                "body_preview": body[:500],
                "html_preview": (html_body or "")[:500] if html_body else None,
                "message": f"Email saved locally — SMTP unavailable ({e})",
                "smtp_error": str(e),
            }

        return {"status": "sent", "to": to, "subject": subject}
