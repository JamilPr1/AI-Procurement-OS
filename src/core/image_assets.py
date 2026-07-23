"""Download and serve product images extracted from buyer websites."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from src.tools.website import USER_AGENT

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
SKIP_NAME_PARTS = ("icon", "logo", "sprite", "pixel", "avatar", "badge", "spinner", "1x1")
SKIP_IMAGE_PATTERNS = (
    "splash", "signup", "sign-up", "sign_up", "plane", "smart-phone", "smartphone",
    "icon", "logo", "banner", "hero", "placeholder", "avatar", "badge",
    "spinner", "loading", "widget", "emoji", "social", "payment", "gravatar",
    "favicon", "tracking", "pixel", "blank", "default", "noimage", "no-image",
    "thumb-", "thumbnail", "wp-smiley", "emoji", "cart", "checkout",
)
MIN_BYTES = 2500
MIN_WIDTH_HINT = 120  # skip tiny assets via URL hints


def is_junk_image(url: str, alt: str = "") -> bool:
    low = f"{url} {alt}".lower()
    if any(p in low for p in SKIP_IMAGE_PATTERNS):
        return True
    if any(p in low for p in SKIP_NAME_PARTS):
        return True
    # Very small dimension hints in CDN URLs
    for dim in ("x16", "x24", "x32", "x48", "x64", "16x16", "32x32", "50x50"):
        if dim in low:
            return True
    return False


def cache_product_images(
    image_candidates: list[dict[str, Any]],
    entity_id: str,
    data_dir: Path,
    *,
    max_images: int = 6,
    base_serve_url: str = "/api/media",
    dashboard_base: str = "http://127.0.0.1:8765",
) -> list[dict[str, Any]]:
    """Download remote images into data/images/{entity_id}/ and return metadata."""
    if not image_candidates:
        return []

    out_dir = data_dir / "images" / entity_id
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()

    with httpx.Client(
        timeout=12,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for cand in image_candidates:
            if len(saved) >= max_images:
                break
            url = (cand.get("url") or "").strip()
            if not url or not url.startswith("http"):
                continue
            low = url.lower()
            if is_junk_image(url, cand.get("alt", "")):
                continue
            if any(p in low for p in SKIP_NAME_PARTS):
                continue
            try:
                r = client.get(url)
                r.raise_for_status()
                content = r.content
            except Exception:
                continue
            if len(content) < MIN_BYTES:
                continue
            digest = hashlib.sha1(content).hexdigest()[:12]
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)
            ext = _ext_from_url_or_type(url, r.headers.get("content-type", ""))
            filename = f"{len(saved) + 1}_{digest}{ext}"
            path = out_dir / filename
            path.write_bytes(content)
            saved.append({
                "filename": filename,
                "url": url,
                "alt": cand.get("alt") or "Product image",
                "source_page": cand.get("source_page", ""),
                "local_path": str(path),
                "serve_url": f"{dashboard_base.rstrip('/')}{base_serve_url}/{entity_id}/{filename}",
            })
    return saved


def _ext_from_url_or_type(url: str, content_type: str) -> str:
    path = urlparse(url).path.lower()
    for ext in ALLOWED_EXT:
        if path.endswith(ext):
            return ext
    ct = (content_type or "").lower()
    if "png" in ct:
        return ".png"
    if "webp" in ct:
        return ".webp"
    if "gif" in ct:
        return ".gif"
    return ".jpg"


def images_html_block(images: list[dict[str, Any]], *, heading: str = "Factory-direct products we can source for your programs") -> str:
    if not images:
        return ""
    tags = []
    for img in images[:4]:
        src = img.get("serve_url") or img.get("url", "")
        if not src:
            continue
        alt = re.sub(r"[^\w\s-]", "", img.get("alt") or "Product")[:80]
        tags.append(
            f'<img src="{src}" alt="{alt}" '
            f'style="max-width:180px;max-height:140px;margin:6px;border-radius:8px;object-fit:cover;border:1px solid #ddd"/>'
        )
    if not tags:
        return ""
    return (
        f'<p style="margin:16px 0 8px;font-weight:600">{heading}</p>'
        f'<div style="display:flex;flex-wrap:wrap;gap:4px">{"".join(tags)}</div>'
    )
