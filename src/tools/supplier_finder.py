"""Real-time supplier discovery from B2B platforms via web search."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from src.tools.web_search import WebSearch
from src.tools.website import WebsiteFetcher

PRICE_RE = re.compile(
    r"\$\s*(\d+\.?\d*)\s*(?:[-–]\s*\$?\s*(\d+\.?\d*))?\s*/\s*(?:pc|piece|unit|pcs)",
    re.I,
)
PRICE_FALLBACK_RE = re.compile(r"\$\s*(\d+\.?\d*)\s*(?:/|per)\s*(?:pc|piece|unit)", re.I)
MOQ_RE = re.compile(r"MOQ[:\s]*(\d[\d,]*)", re.I)
LEAD_TIME_RE = re.compile(r"(\d+)\s*(?:days?|business days?)", re.I)


class SupplierFinder:
    def __init__(self, config: dict[str, Any]) -> None:
        self.platforms = config.get("discovery", {}).get(
            "supplier_search_platforms",
            ["alibaba.com", "made-in-china.com"],
        )
        pipe = config.get("pipeline", {})
        self.search = WebSearch(
            pause_seconds=pipe.get("search_pause_seconds", 0.2),
            workers=pipe.get("parallel_workers", 6),
        )

    def discover(self, product_keywords: str, max_suppliers: int = 4) -> list[dict[str, Any]]:
        queries = [
            f"custom {product_keywords} manufacturer site:alibaba.com",
            f"{product_keywords} OEM factory site:made-in-china.com",
            f'"{product_keywords}" wholesale manufacturer MOQ',
        ]
        results = self.search.search_many(queries, max_results=5)

        suppliers: list[dict[str, Any]] = []
        seen: set[str] = set()

        for r in results:
            if len(suppliers) >= max_suppliers:
                break
            url = r.get("url", "")
            domain = urlparse(url).netloc.lower()
            # skip generic showroom/category pages
            if any(x in url for x in ("/showroom/", "/search?", "-suppliers.html", "/products-search/", "/topic/")):
                continue
            key = urlparse(url).path[:80] or domain
            if key in seen:
                continue
            seen.add(key)

            snippet = r.get("snippet", "") + " " + r.get("title", "")
            factory_name = self._extract_factory_name(r.get("title", ""), url)
            price = self._extract_price(snippet)
            moq = self._extract_moq(snippet)
            lead_time = self._extract_lead_time(snippet)

            platform = "web"
            for p in self.platforms:
                if p.replace("www.", "") in domain:
                    platform = p
                    break

            supplier = {
                "factory_name": factory_name,
                "platform_source": platform,
                "url": url,
                "moq": moq,
                "unit_price_estimate_usd": price,
                "certifications": self._extract_certs(snippet),
                "years_in_business": 0,
                "export_countries": [],
                "search_snippet": snippet[:500],
                "lead_time_days": lead_time,
                "source": "duckduckgo_web_search",
            }
            suppliers.append(supplier)

        return suppliers

    def _extract_factory_name(self, title: str, url: str) -> str:
        if title:
            name = re.split(r"[\|–—\-:]", title)[0].strip()
            if len(name) > 3:
                return name[:120]
        path = urlparse(url).path.strip("/").split("/")
        if path:
            return path[-1].replace("-", " ").title()[:120]
        return urlparse(url).netloc

    def _extract_price(self, text: str) -> float:
        m = PRICE_RE.search(text) or PRICE_FALLBACK_RE.search(text)
        if m:
            try:
                low = float(m.group(1))
                high = float(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else low
                val = (low + high) / 2
                if 0.1 < val < 100:
                    return round(val, 2)
            except (ValueError, TypeError):
                pass
        return 0.0

    def _extract_moq(self, text: str) -> int:
        m = MOQ_RE.search(text)
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except ValueError:
                pass
        for m in re.finditer(r"(\d{2,6})\s*(?:pieces|pcs|units)", text, re.I):
            val = int(m.group(1))
            if 100 <= val <= 100000:
                return val
        return 0

    def _extract_lead_time(self, text: str) -> int:
        m = LEAD_TIME_RE.search(text)
        if m:
            return int(m.group(1))
        return 0

    def _extract_certs(self, text: str) -> list[str]:
        certs = []
        for c in ("FDA", "LFGB", "CE", "RoHS", "ISO9001", "ISO 9001", "BSCI", "SGS"):
            if c.lower() in text.lower():
                certs.append(c)
        return certs
