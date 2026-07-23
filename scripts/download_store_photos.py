"""Download and verify real product photos for storefronts."""

from __future__ import annotations

import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src" / "web" / "store-products"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Burst (Shopify), Pixabay CDN, and Wikimedia — product-focused URLs
CANDIDATES: dict[str, list[str]] = {
    "ceramic-mug.jpg": [
        "https://cdn.shopify.com/s/files/1/0533/2089/files/placeholder-images-image_large.png",  # fallback skip
        "https://images.pexels.com/photos/1566307/pexels-photo-1566307.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/1005038/pexels-photo-1005038.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/2396220/pexels-photo-2396220.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "vacuum-tumbler.jpg": [
        "https://images.pexels.com/photos/39362/two-brown-and-blue-ceramic-mugs-39362.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/1283219/pexels-photo-1283219.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/285932/pexels-photo-285932.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "water-bottle.jpg": [
        "https://images.pexels.com/photos/416528/pexels-photo-416528.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/1552611/pexels-photo-1552611.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/903661/pexels-photo-903661.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "promo-tote.jpg": [
        "https://images.pexels.com/photos/2905238/pexels-photo-2905238.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/1005638/pexels-photo-1005638.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/1556706/pexels-photo-1556706.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "powder-tumbler.jpg": [
        "https://images.pexels.com/photos/285932/pexels-photo-285932.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/1283219/pexels-photo-1283219.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "travel-mug.jpg": [
        "https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/1006302/pexels-photo-1006302.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/414630/pexels-photo-414630.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "wine-tumbler.jpg": [
        "https://images.pexels.com/photos/1407846/pexels-photo-1407846.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/602750/pexels-photo-602750.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "polo-shirt.jpg": [
        "https://images.pexels.com/photos/6311477/pexels-photo-6311477.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/7671166/pexels-photo-7671166.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "gift-box.jpg": [
        "https://images.pexels.com/photos/669361/pexels-photo-669361.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/1939485/pexels-photo-1939485.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "journal.jpg": [
        "https://images.pexels.com/photos/669996/pexels-photo-669996.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/261763/pexels-photo-261763.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "pen-set.jpg": [
        "https://images.pexels.com/photos/4488640/pexels-photo-4488640.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/279906/pexels-photo-279906.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "safety-vest.jpg": [
        "https://images.pexels.com/photos/3862132/pexels-photo-3862132.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/9258892/pexels-photo-9258892.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "hard-hat.jpg": [
        "https://images.pexels.com/photos/3862139/pexels-photo-3862139.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/162553/pexels-photo-162553.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "work-polo.jpg": [
        "https://images.pexels.com/photos/6311392/pexels-photo-6311392.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/7671166/pexels-photo-7671166.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "softshell-jacket.jpg": [
        "https://images.pexels.com/photos/984324/pexels-photo-984324.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/1925621/pexels-photo-1925621.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "lanyard-badge.jpg": [
        "https://images.pexels.com/photos/7688336/pexels-photo-7688336.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/7688161/pexels-photo-7688161.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "conference-tee.jpg": [
        "https://images.pexels.com/photos/2897380/pexels-photo-2897380.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/996329/pexels-photo-996329.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
    "banner-stand.jpg": [
        "https://images.pexels.com/photos/2774556/pexels-photo-2774556.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
        "https://images.pexels.com/photos/3184296/pexels-photo-3184296.jpeg?auto=compress&cs=tinysrgb&w=640&h=420&fit=crop",
    ],
}


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = resp.read()
    if len(data) < 5000:
        raise ValueError(f"too small ({len(data)} bytes)")
    if data[:2] != b"\xff\xd8" and not data.startswith(b"\x89PNG"):
        raise ValueError("not a JPEG/PNG")
    return data


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, urls in CANDIDATES.items():
        saved = False
        for url in urls:
            if "placeholder" in url:
                continue
            try:
                blob = download(url)
                (OUT / fname).write_bytes(blob)
                print(f"OK  {fname} <- {url.split('/photos/')[1].split('/')[0] if '/photos/' in url else url}")
                saved = True
                break
            except Exception as exc:
                print(f"skip {fname}: {exc}")
        if not saved:
            print(f"FAIL {fname}")


if __name__ == "__main__":
    main()
