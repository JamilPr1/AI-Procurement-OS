"""Fast parallel lead discovery — US market, buyer-intent platforms."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urlparse

from src.core.company_name import resolve_company_name
from src.tools.us_market import is_us_market
from src.tools.web_search import WebSearch
from src.tools.website import WebsiteFetcher

SKIP_DOMAINS = {
    "facebook.com", "twitter.com", "x.com", "instagram.com",
    "youtube.com", "yelp.com", "bbb.org", "wikipedia.org", "amazon.com",
    "alibaba.com", "made-in-china.com", "globalsources.com", "1688.com",
    "pinterest.com", "tiktok.com", "indeed.com", "glassdoor.com",
    "google.com", "bing.com", "duckduckgo.com",
    "paavri.com", "ensun.io", "clutch.co", "g2.com", "capterra.com",
    "thomasnet.com", "manta.com", "dnb.com", "zoominfo.com",
    "supplyia.com", "perfectimprints.com", "statista.com",
    "faire.com", "wholesalecentral.com", "wholesale.com", "dhgate.com",
    "aliexpress.com", "indiamart.com", "tradeindia.com", "ec21.com",
}

# Allowed when result comes from buyer-intent search (people posting RFQs / looking to buy)
INTENT_PLATFORM_DOMAINS = {
    "reddit.com", "old.reddit.com", "linkedin.com", "quora.com",
    "govcb.com", "demandstar.com", "sam.gov", "mfg.com", "globalspec.com",
    "rfqmarketplace.com", "sourcify.com", "freelancer.com", "upwork.com",
}

LISTICLE_KEYWORDS = (
    "top 100", "top 50", "top 10", "best ", "list of", "directory",
    "who is the", "how to choose", "how to find", "guide to", "ranking",
    "statistics", "industry sales", "suppliers in", "companies in",
)

BUYER_INTENT_PHRASES = (
    "looking for supplier", "looking for manufacturer", "need a manufacturer",
    "request for quote", "request for quotation", "rfq", "bulk order",
    "wholesale order", "sourcing agent", "where to buy bulk", "need supplier",
    "seeking supplier", "want to order", "purchase order", "bulk purchase",
    "custom order", "oem partner", "private label",
)


class LeadFinder:
    def __init__(self, config: dict[str, Any]) -> None:
        disc = config.get("discovery", {})
        pipe = config.get("pipeline", {})
        self.region = disc.get("region", "United States")
        self.us_only = disc.get("us_only", True)
        self.max_leads = disc.get("max_leads", 20)
        self.max_candidates = disc.get("max_candidates", 80)
        self.results_per_query = disc.get("results_per_query", 8)
        self.buyer_types = disc.get("buyer_types", ["promotional products distributor"])
        self.known = disc.get("known_distributors", [])
        self.intent_queries = disc.get("buyer_intent_queries", [])
        self.skip_contact = disc.get("skip_contact_during_discovery", False)
        workers = pipe.get("parallel_workers", 8)
        pause = pipe.get("search_pause_seconds", 0.2)
        self.search = WebSearch(pause_seconds=pause, workers=workers, region="us-en")
        self.fetcher = WebsiteFetcher(timeout=8)
        self.workers = workers

    def discover(self, on_progress=None, niche: dict | None = None) -> list[dict[str, Any]]:
        niche = niche or {}
        buyer_types = niche.get("buyer_search_queries") or niche.get("buyer_types") or self.buyer_types
        product_kw = (niche.get("product_keywords") or ["promotional products"])[0]

        queries = self._build_distributor_queries(buyer_types)
        queries.extend(self._build_intent_queries(product_kw, niche.get("niche_name", "")))
        queries.extend(self.intent_queries)

        if on_progress:
            on_progress("searching", f"Running {len(queries)} US-focused searches...")
        candidates = self.search.search_parallel(queries, max_results=self.results_per_query)
        candidates = candidates[: self.max_candidates]

        leads: list[dict[str, Any]] = []
        seen: set[str] = set()
        qualify_timeout = 20.0

        def process(result: dict) -> dict | None:
            url = result.get("url", "")
            domain = urlparse(url).netloc.lower().replace("www.", "")
            if not domain or domain in seen:
                return None

            is_intent = self._is_intent_platform(domain) or result.get("intent_platform")
            if not is_intent and any(skip in domain for skip in SKIP_DOMAINS):
                return None
            if "/blog/" in url.lower() and "blog" in domain and not is_intent:
                return None

            seen.add(domain if not is_intent else url)

            if is_intent:
                return self._lead_from_intent_post(result, domain, url)

            site = self.fetcher.fetch(url)
            if not site.get("reachable"):
                return None
            emails = site.get("emails") or []
            phones = site.get("phones") or []
            if not self.skip_contact and not emails and not phones:
                contact = self.fetcher.find_contact_page(url)
                if contact:
                    emails = contact.get("emails") or []
                    phones = contact.get("phones") or []

            text_blob = " ".join([
                result.get("snippet", ""),
                site.get("text_preview", ""),
                site.get("meta_description", ""),
                site.get("title", ""),
                result.get("title", ""),
            ])
            if self.us_only and not is_us_market(
                domain=domain,
                text=text_blob,
                phones=phones,
                emails=emails,
                strict=True,
            ):
                return None

            name = self._company_name(
                site.get("title", ""), result.get("title", ""), domain,
                emails[0] if emails else "",
            )
            if self._is_listicle(name, domain, text_blob, url):
                return None
            if self._is_marketplace_page(name, domain, url):
                return None

            lead = {
                "company_name": name,
                "website": site.get("url", url),
                "domain": domain,
                "email": emails[0] if emails else "",
                "emails_found": emails,
                "phone": phones[0] if phones else "",
                "phones_found": phones,
                "industry": self._guess_industry(result.get("snippet", ""), site.get("text_preview", "")),
                "source": "live_web_search",
                "source_platform": "web",
                "market": "US",
                "source_query": result.get("source_query", ""),
                "search_snippet": result.get("snippet", ""),
                "website_title": site.get("title", ""),
                "meta_description": site.get("meta_description", ""),
                "website_text_preview": (site.get("text_preview") or "")[:1500],
                "image_candidates": site.get("image_candidates") or [],
                "niche": niche.get("niche_name", ""),
                "region": self.region,
            }
            lead["lead_score"] = self._score(lead)
            return lead

        if on_progress:
            on_progress("fetching", f"Qualifying {len(candidates)} US buyer candidates...")

        checked = 0
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futs = [pool.submit(process, r) for r in candidates]
            for fut in as_completed(futs):
                if len(leads) >= self.max_leads:
                    break
                checked += 1
                try:
                    lead = fut.result(timeout=qualify_timeout)
                except Exception:
                    lead = None
                if lead:
                    leads.append(lead)
                if on_progress and (checked % 5 == 0 or len(leads) >= self.max_leads):
                    on_progress(
                        "fetching",
                        f"Qualified {len(leads)} leads ({min(checked, len(candidates))}/{len(candidates)} checked)...",
                    )

        leads.sort(key=lambda x: x["lead_score"], reverse=True)
        return leads[: self.max_leads]

    def _build_distributor_queries(self, buyer_types: list[str]) -> list[str]:
        queries: list[str] = []
        for bt in buyer_types:
            q = bt.strip()
            if not q:
                continue
            queries.append(q)
            lower = q.lower()
            if "usa" not in lower and "united states" not in lower:
                queries.append(f"{q} USA")
        for domain in self.known:
            queries.append(f"site:{domain} promotional products")
        queries += [
            "ASI promotional products distributor USA",
            "PPAI member distributor promotional products USA",
            "SAGE promotional products distributor United States",
            "custom promotional products wholesaler USA contact",
            "corporate gifts distributor United States email",
            "branded merchandise distributor USA wholesale",
        ]
        return queries

    def _build_intent_queries(self, product_kw: str, niche_name: str) -> list[str]:
        product = product_kw or "promotional products"
        niche = niche_name or product
        us = "USA"
        templates = [
            f'site:reddit.com "looking for" manufacturer {product} {us}',
            f'site:reddit.com bulk order {product} supplier {us}',
            f'site:reddit.com "need supplier" {product} United States',
            f'site:linkedin.com/posts sourcing {product} {us}',
            f'site:linkedin.com/posts "request for quote" {product}',
            f'site:quora.com where to buy bulk {product} {us}',
            f'site:quora.com "looking for manufacturer" {product} United States',
            f'"request for quote" {product} buyer United States',
            f'"looking for supplier" bulk {product} {us}',
            f'site:mfg.com RFQ {product}',
            f'site:globalspec.com {product} buyer RFQ',
            f'site:govcb.com {product} RFQ',
            f'site:demandstar.com promotional products',
            f'site:sam.gov promotional products',
            f'"bulk order" {niche} distributor {us}',
            f'"wholesale inquiry" custom {product} {us}',
            f'site:facebook.com/groups promotional products distributor {us}',
        ]
        return templates

    def _is_intent_platform(self, domain: str) -> bool:
        return any(domain == p or domain.endswith("." + p) for p in INTENT_PLATFORM_DOMAINS)

    def _lead_from_intent_post(self, result: dict, domain: str, url: str) -> dict | None:
        snippet = result.get("snippet", "") or ""
        title = result.get("title", "") or ""
        blob = f"{title} {snippet}".lower()

        if not any(p in blob for p in BUYER_INTENT_PHRASES):
            if not any(k in blob for k in ("rfq", "bulk", "wholesale", "sourcing", "supplier", "manufacturer")):
                return None

        if self.us_only and not is_us_market(domain=domain, text=blob, phones=None, emails=None, strict=True):
            return None

        platform = domain.split(".")[0] if domain else "intent"
        name = self._name_from_intent(title, snippet, platform)

        lead = {
            "company_name": name,
            "website": url,
            "domain": domain,
            "email": "",
            "emails_found": [],
            "phone": "",
            "phones_found": [],
            "industry": "buyer_intent",
            "source": f"buyer_intent_{platform}",
            "source_platform": platform,
            "market": "US",
            "source_query": result.get("source_query", ""),
            "search_snippet": snippet[:500],
            "website_title": title,
            "meta_description": snippet[:300],
            "website_text_preview": snippet[:1500],
            "image_candidates": [],
            "niche": "",
            "region": self.region,
            "intent_url": url,
        }
        lead["lead_score"] = self._score(lead, intent=True)
        return lead

    def _name_from_intent(self, title: str, snippet: str, platform: str) -> str:
        for raw in (title, snippet):
            if not raw:
                continue
            cleaned = re.sub(r"\s*[-|–—]\s*(Reddit|LinkedIn|Quora|Facebook).*$", "", raw, flags=re.I)
            cleaned = re.sub(r"^r/\w+\s*", "", cleaned)
            cleaned = cleaned.strip()
            if 8 < len(cleaned) < 90:
                return cleaned[:80]
        return f"{platform.title()} buyer inquiry"

    def _is_listicle(self, name: str, domain: str, snippet: str, url: str) -> bool:
        text = f"{name} {snippet} {url}".lower()
        if any(k in text for k in LISTICLE_KEYWORDS):
            return True
        if "/blog/" in url.lower() or "/statistics/" in url.lower():
            return True
        return False

    def _is_marketplace_page(self, name: str, domain: str, url: str) -> bool:
        text = f"{name} {url}".lower()
        if any(k in text for k in ("discover thousands", "shop wholesale online", "sign up to sell")):
            return True
        if "/suppliers/" in url.lower() or "/marketplace" in url.lower():
            return True
        return False

    def _company_name(self, site_title: str, result_title: str, domain: str, email: str = "") -> str:
        return resolve_company_name(
            title=site_title or result_title,
            domain=domain,
            email=email,
        )

    def _guess_industry(self, snippet: str, text: str) -> str:
        c = (snippet + text).lower()
        if "corporate gift" in c:
            return "corporate_gifts"
        if "promotional" in c or "branded" in c:
            return "promotional_products"
        return "promotional_products"

    def _score(self, lead: dict, *, intent: bool = False) -> float:
        score = 25.0 if intent else 30.0
        text = (lead.get("website_text_preview", "") + lead.get("search_snippet", "")).lower()
        domain = lead.get("domain", "")
        if lead.get("email"):
            score += 25
        if lead.get("phone"):
            score += 10
        if lead.get("market") == "US":
            score += 5
        if any(k in text for k in BUYER_INTENT_PHRASES):
            score += 15
        if any(k in text for k in ("distributor", "wholesale", "catalog", "custom", "branded", "bulk", "rfq")):
            score += 12
        if any(k in domain for k in ("promo", "gift", "brand", "imprint", "merch")):
            score += 8
        if domain in self.known or any(k in domain for k in self.known):
            score += 15
        if len(lead.get("website_text_preview", "")) > 400:
            score += 5
        if intent and lead.get("source_platform") in ("reddit", "linkedin", "mfg", "globalspec"):
            score += 8
        return min(score, 100.0)
