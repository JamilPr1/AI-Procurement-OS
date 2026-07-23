"""Fetch and parse real company websites."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
)
SKIP_EMAIL_SUFFIXES = (".png", ".jpg", ".gif", ".svg", ".webp", "example.com", "sentry.io", "wixpress.com")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class WebsiteFetcher:
    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout

    def fetch(self, url: str) -> dict[str, Any]:
        if not url.startswith("http"):
            url = f"https://{url}"
        try:
            with httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                r = client.get(url)
                r.raise_for_status()
                html = r.text
                final_url = str(r.url)
        except Exception as e:
            return {"url": url, "error": str(e), "reachable": False}

        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        title = soup.title.get_text(strip=True) if soup.title else ""
        meta_desc = ""
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            meta_desc = meta["content"].strip()

        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)[:8000]

        emails = self._extract_emails(html, final_url)
        phones = list({p.strip() for p in PHONE_RE.findall(html)})[:5]
        image_candidates = self._extract_image_candidates(soup, final_url)

        return {
            "url": final_url,
            "reachable": True,
            "title": title,
            "meta_description": meta_desc,
            "text_preview": text[:3000],
            "emails": emails,
            "phones": phones,
            "domain": urlparse(final_url).netloc,
            "image_candidates": image_candidates,
        }

    def _extract_emails(self, html: str, base_url: str) -> list[str]:
        found: set[str] = set()
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip()
                if self._valid_email(email):
                    found.add(email.lower())
        for match in EMAIL_RE.findall(html):
            if self._valid_email(match):
                found.add(match.lower())
        return sorted(found)[:5]

    @staticmethod
    def _valid_email(email: str) -> bool:
        email = email.lower()
        if any(email.endswith(s) for s in SKIP_EMAIL_SUFFIXES):
            return False
        if "@" not in email or len(email) > 80:
            return False
        local, _, domain = email.partition("@")
        if not local or not domain or "." not in domain:
            return False
        return True

    def _extract_image_candidates(self, soup: BeautifulSoup, base_url: str) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []

        def add(raw: str, alt: str = "") -> None:
            if not raw or raw.startswith("data:"):
                return
            url = urljoin(base_url, raw.strip())
            low = url.lower()
            junk = any(x in low for x in (
                "icon", "logo", "sprite", "pixel", "avatar", "badge", "spinner", "1x1", ".svg",
                "splash", "signup", "placeholder", "banner", "hero", "widget", "favicon",
            ))
            alt_low = (alt or "").lower()
            if junk or any(x in alt_low for x in ("splash", "signup", "icon", "logo", "plane")):
                return
            if url in seen:
                return
            seen.add(url)
            out.append({"url": url, "alt": (alt or "").strip()[:120], "source_page": base_url})

        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            add(og["content"], "Featured product")
        for img in soup.find_all("img"):
            src = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-lazy-src")
                or img.get("data-original")
                or ""
            )
            if not src and img.get("srcset"):
                src = img["srcset"].split(",")[0].strip().split(" ")[0]
            add(src, img.get("alt", ""))
        return out[:20]

    def find_contact_page(self, base_url: str) -> dict[str, Any] | None:
        """Try /contact page for more emails."""
        parsed = urlparse(base_url if base_url.startswith("http") else f"https://{base_url}")
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path in ("/contact", "/contact-us", "/about/contact"):
            result = self.fetch(urljoin(base, path))
            if result.get("reachable") and (result.get("emails") or result.get("phones")):
                return result
        return None
