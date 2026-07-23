"""Discover high-opportunity buyer niches before lead discovery."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from src.tools.web_search import WebSearch

NICHE_QUERIES = [
    "trending promotional products distributors buy 2025 2026",
    "fastest growing corporate gift categories wholesale USA",
    "top selling custom drinkware promotional products",
    "school university promotional product trends",
    "construction company branded merchandise trends",
]

PRODUCT_SIGNALS = {
    "drinkware": ("drinkware", "tumbler", "water bottle", "mug", "cup", "insulated"),
    "apparel": ("apparel", "shirt", "polo", "hoodie", "jacket", "uniform"),
    "bags": ("tote", "backpack", "bag", "duffel"),
    "writing": ("pen", "pencil", "stationery"),
    "tech": ("power bank", "usb", "charger", "tech gift"),
    "wellness": ("lip balm", "sanitizer", "wellness", "fitness"),
    "outdoor": ("cooler", "camping", "outdoor", "blanket"),
}


class NicheFinder:
    def __init__(self, config: dict[str, Any]) -> None:
        disc = config.get("discovery", {})
        pipe = config.get("pipeline", {})
        self.region = disc.get("region", "United States")
        self.vertical = config.get("vertical", {}).get("display_name", "Promotional Products")
        pause = pipe.get("search_pause_seconds", 0.2)
        workers = pipe.get("parallel_workers", 4)
        self.search = WebSearch(pause_seconds=pause, workers=workers, region="us-en")

    def find_top_niche(self, on_progress=None) -> dict[str, Any]:
        if on_progress:
            on_progress("searching", f"Scanning {len(NICHE_QUERIES)} niche trend queries...")
        results = self.search.search_parallel(NICHE_QUERIES, max_results=4)
        text = " ".join(
            f"{r.get('title', '')} {r.get('snippet', '')}" for r in results
        ).lower()

        scores: Counter[str] = Counter()
        for niche, keywords in PRODUCT_SIGNALS.items():
            scores[niche] = sum(text.count(k) for k in keywords)

        top_niche = scores.most_common(1)[0][0] if scores else "drinkware"
        niche_labels = {
            "drinkware": "Custom drinkware & tumblers",
            "apparel": "Branded apparel & uniforms",
            "bags": "Promotional bags & totes",
            "writing": "Branded writing instruments",
            "tech": "Tech & gadget gifts",
            "wellness": "Wellness & personal care promos",
            "outdoor": "Outdoor & lifestyle products",
        }
        niche_name = niche_labels.get(top_niche, top_niche.title())
        keywords = list(PRODUCT_SIGNALS.get(top_niche, PRODUCT_SIGNALS["drinkware"]))

        buyer_queries = [
            f"{niche_name} distributor USA",
            f"custom {keywords[0]} wholesaler United States",
            f"promotional {keywords[0]} catalog distributor USA",
            f"corporate gifts {keywords[0]} buyer USA",
            f"bulk {keywords[0]} RFQ United States",
        ]
        buyer_types = buyer_queries + [
            f"promotional products distributor USA",
            f"corporate gifts distributor United States",
        ]

        return {
            "niche_id": top_niche,
            "niche_name": niche_name,
            "niche_score": min(100, 60 + scores[top_niche] * 3),
            "product_keywords": keywords[:5],
            "buyer_search_queries": buyer_types[:6],
            "buyer_types": buyer_types[:6],
            "region": self.region,
            "rationale": (
                f"Based on live web signals, {niche_name} shows the strongest demand among "
                f"{self.vertical} buyers in {self.region}. Lead discovery will target matching distributors."
            ),
            "source": "niche_finder",
            "trend_snippets": [r.get("snippet", "")[:160] for r in results[:3]],
        }
