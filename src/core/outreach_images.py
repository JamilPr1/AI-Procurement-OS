"""Factory / supplier product images for outreach emails — not buyer website junk."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from src.core.hot_leads import match_suppliers
from src.core.image_assets import cache_product_images, is_junk_image
from src.tools.web_search import WebSearch
from src.tools.website import WebsiteFetcher

FACTORY_IMAGE_HEADING = "Factory-direct products we can source for your programs"

SKIP_URL_PATHS = (
    "/blog/", "/topic/", "/guide", "/news/", "/article/",
    "-suppliers.html", "/search?", "/showroom/",
)


def _supplier_page_images(fetcher: WebsiteFetcher, supplier: dict, *, product_label: str) -> list[dict]:
    url = (supplier.get("url") or "").strip()
    if not url or not url.startswith("http"):
        return []
    low = url.lower()
    if any(p in low for p in SKIP_URL_PATHS):
        return []

    page = fetcher.fetch(url)
    if not page.get("reachable"):
        return []

    factory = supplier.get("factory_name") or "Factory"
    out: list[dict] = []
    for img in page.get("image_candidates") or []:
        img_url = img.get("url") or ""
        alt = img.get("alt") or ""
        if is_junk_image(img_url, alt):
            continue
        out.append({
            **img,
            "alt": f"{factory} — {alt or product_label}",
            "factory_name": factory,
            "source": "factory_catalog",
        })
    return out


def _alibaba_product_images(fetcher: WebsiteFetcher, primary_need: str, *, limit: int = 8) -> list[dict]:
    if not primary_need:
        return []
    search = WebSearch(pause_seconds=0.15, workers=2)
    queries = [
        f"custom {primary_need} tumbler site:alibaba.com/product",
        f"{primary_need} OEM manufacturer product site:alibaba.com",
    ]
    candidates: list[dict] = []
    seen_urls: set[str] = set()

    for query in queries:
        for r in search.search(query, max_results=6):
            url = r.get("url") or ""
            if not url or url in seen_urls:
                continue
            if "alibaba.com" not in url.lower():
                continue
            if "/product-detail/" not in url and "/product/" not in url:
                continue
            seen_urls.add(url)
            page = fetcher.fetch(url)
            if not page.get("reachable"):
                continue
            for img in page.get("image_candidates") or []:
                img_url = img.get("url") or ""
                if is_junk_image(img_url, img.get("alt", "")):
                    continue
                candidates.append({
                    **img,
                    "alt": f"Factory reference — {primary_need}",
                    "factory_name": "Verified supplier",
                    "source": "alibaba_product",
                })
            if len(candidates) >= limit:
                return candidates
    return candidates


def fetch_factory_catalog_images(
    supplier_matches: list[dict],
    entity_id: str,
    data_dir: Any,
    *,
    primary_need: str = "",
    max_images: int = 4,
    dashboard_base: str = "http://127.0.0.1:8765",
) -> list[dict]:
    """Download product photos from matched factory URLs and Alibaba listings."""
    fetcher = WebsiteFetcher(timeout=10)
    candidates: list[dict] = []
    seen: set[str] = set()

    def add_batch(batch: list[dict]) -> None:
        for img in batch:
            url = img.get("url") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            candidates.append(img)

    for sup in supplier_matches[:5]:
        add_batch(_supplier_page_images(fetcher, sup, product_label=primary_need or "product"))
        if len(candidates) >= max_images * 3:
            break

    if len(candidates) < max_images:
        add_batch(_alibaba_product_images(fetcher, primary_need, limit=max_images * 3))

    if not candidates:
        return []

    return cache_product_images(
        candidates,
        entity_id,
        data_dir,
        max_images=max_images,
        dashboard_base=dashboard_base,
    )


def resolve_outreach_images(
    lead_id: str,
    lead: dict,
    intent: dict,
    storage: Any,
    tenant_id: str,
    *,
    dashboard_base: str = "http://127.0.0.1:8765",
    force_refresh: bool = False,
) -> list[dict]:
    """Pick factory product images for outreach — never buyer website splash assets."""
    primary = intent.get("primary_need") or "promotional products"
    cache_key = f"{primary}:{intent.get('intent_strength', 0)}"

    if not force_refresh:
        cached = storage.load_json_entity("outreach_images", lead_id)
        if cached and cached.get("cache_key") == cache_key and cached.get("images"):
            return cached["images"]

    suppliers = storage.list_suppliers(tenant_id, limit=200)
    matches = match_suppliers(intent, suppliers, limit=6)

    if not matches and intent.get("recommended_supplier"):
        matches = [intent["recommended_supplier"]]

    images = fetch_factory_catalog_images(
        matches,
        lead_id,
        storage.data_dir,
        primary_need=primary,
        max_images=4,
        dashboard_base=dashboard_base,
    )

    storage.save_json_entity("outreach_images", lead_id, {
        "cache_key": cache_key,
        "primary_need": primary,
        "images": images,
        "supplier_count": len(matches),
        "factories": [m.get("factory_name") for m in matches[:4]],
    })
    return images
